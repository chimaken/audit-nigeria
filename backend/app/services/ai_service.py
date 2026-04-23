"""Vision extraction for INEC EC8A-style forms via OpenRouter or AWS Bedrock."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

# Used when primary OPENROUTER_MODEL returns 404 "No endpoints" (provider routing).
_OPENROUTER_MODEL_FALLBACKS: tuple[str, ...] = (
    "anthropic/claude-sonnet-4.5",
    "google/gemini-2.0-flash-001",
    "openai/gpt-4o-mini",
)

SYSTEM_PROMPT = """You are a forensic election auditor. Your task is to extract data from this Nigerian INEC results form (EC8A family).

## Step 1 — Form header (location metadata)

Before extracting votes, read the **printed header** on the form and populate `form_header`:

- "state": string (e.g. Lagos, Federal Capital Territory)
- "lga": string (Local Government Area name as printed)
- "ward": string (ward label or number as printed, e.g. "Ward 03" or "03")
- "pu_name": string (polling unit name / description as printed)
- "pu_code": string — INEC polling unit code in the form **StateCode-LGACode-WardCode-UnitNumber** using two digits per segment except the final segment which is three digits (e.g. 24-11-03-001). Preserve leading zeros. If the sheet uses spaces or slashes, normalize to hyphen-separated digits.
- "election_type": string — classify the form: "EC8A" (general PU result / presidential or state assembly style sheet), "EC8A(i)" (Senate), or "EC8A(ii)" (House of Representatives). If unclear, use "EC8A".

Use empty string only when a field is truly missing or unreadable.

## Step 2 — Party votes and summary

Each party row has votes **in figures** (digits) and **in words** (English words, e.g. "Forty two"). Extract BOTH for every party listed (A, AA, AAC, ADC, ADP, APC, APGA, APM, APP, BP, LP, NNPP, NRM, PDP, PRP, SDP, YPP, ZLP, and any others on the sheet).

If the words cell is blank or completely illegible, use an empty string for that party in party_in_words.

Also extract the three totals rows: Total Valid Votes, Rejected Votes, Total Votes Cast — both figures (integers) and the **in words** text for each row into summary_in_words (use keys total_valid, rejected, total_cast). Use empty string when the words cell is missing.

Verify: Sum of party figures + Rejected Votes == Total Votes Cast (compare using figures).

Return strictly valid JSON with this shape (include form_header at the top level):
{"form_header": {"state": "", "lga": "", "ward": "", "pu_name": "", "pu_code": "", "election_type": ""}, "party_results": {"PARTY": int}, "party_in_words": {"PARTY": ""}, "summary": {"total_valid": int, "rejected": int, "total_cast": int}, "summary_in_words": {"total_valid": "", "rejected": "", "total_cast": ""}, "is_math_correct": boolean}"""


class FormHeader(BaseModel):
    """EC8A printed header — used for dynamic geography and audit display."""

    state: str = ""
    lga: str = ""
    ward: str = ""
    pu_name: str = ""
    pu_code: str = ""
    election_type: str = ""

    @field_validator(
        "state",
        "lga",
        "ward",
        "pu_name",
        "pu_code",
        "election_type",
        mode="before",
    )
    @classmethod
    def _strip_strings(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("election_type", mode="after")
    @classmethod
    def _normalize_election_type(cls, v: str) -> str:
        t = (v or "").strip()
        if not t:
            return "EC8A"
        tl = t.lower()
        if "ec8a(ii)" in tl or "reps" in tl or "representatives" in tl:
            return "EC8A(ii)"
        if "ec8a(i)" in tl or "senate" in tl:
            return "EC8A(i)"
        if "ec8a" in tl:
            return "EC8A"
        return t.upper() if len(t) <= 12 else t[:12]


class ExtractionResult(BaseModel):
    form_header: FormHeader = Field(default_factory=FormHeader)
    party_results: dict[str, int] = Field(default_factory=dict)
    party_in_words: dict[str, str] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)
    summary_in_words: dict[str, str] = Field(default_factory=dict)
    is_math_correct: bool = False

    @field_validator("form_header", mode="before")
    @classmethod
    def _coerce_form_header(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            return {}
        return v

    @field_validator("party_results", mode="before")
    @classmethod
    def _coerce_party_keys_upper(cls, v: Any) -> dict[str, int]:
        if not isinstance(v, dict):
            return {}
        out: dict[str, int] = {}
        for k, val in v.items():
            key = str(k).strip().upper()
            try:
                out[key] = int(val)
            except (TypeError, ValueError):
                continue
        return out

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_summary(cls, v: Any) -> dict[str, int]:
        if not isinstance(v, dict):
            return {}
        mapping = {
            "total_valid": ("total_valid", "Total Valid Votes"),
            "rejected": ("rejected", "Rejected Votes"),
            "total_cast": ("total_cast", "Total Votes Cast"),
        }
        out: dict[str, int] = {}
        for canon, keys in mapping.items():
            for key in keys:
                if key in v:
                    try:
                        out[canon] = int(v[key])
                    except (TypeError, ValueError):
                        pass
                    break
        return out

    @field_validator("party_in_words", mode="before")
    @classmethod
    def _coerce_party_words(cls, v: Any) -> dict[str, str]:
        if not isinstance(v, dict):
            return {}
        out: dict[str, str] = {}
        for k, val in v.items():
            key = str(k).strip().upper()
            if val is None:
                out[key] = ""
            else:
                out[key] = str(val).strip()
        return out

    @field_validator("summary_in_words", mode="before")
    @classmethod
    def _coerce_summary_words(cls, v: Any) -> dict[str, str]:
        if not isinstance(v, dict):
            return {}
        aliases = {
            "total_valid": "total_valid",
            "totalvalidvotes": "total_valid",
            "total_valid_votes": "total_valid",
            "rejected": "rejected",
            "rejectedvotes": "rejected",
            "rejected_votes": "rejected",
            "total_cast": "total_cast",
            "totalvotescast": "total_cast",
            "total_votes_cast": "total_cast",
        }
        out: dict[str, str] = {}
        for k, val in v.items():
            nk = str(k).strip().lower().replace(" ", "_").replace("-", "_")
            canon = aliases.get(nk)
            if canon is None:
                continue
            out[canon] = "" if val is None else str(val).strip()
        return out


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _parse_extraction_json(text: str) -> dict[str, Any]:
    raw = _strip_json_fence(text)
    return json.loads(raw)


async def extract_results_from_image_bytes(image_bytes: bytes, mime: str = "image/jpeg") -> ExtractionResult:
    """
    Call OpenRouter (vision model from settings, with automatic fallbacks) or Bedrock if configured.
    """
    if settings.USE_AWS_BEDROCK:
        return await _extract_bedrock(image_bytes, mime)
    return await _extract_openrouter(image_bytes, mime)


async def _post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    json_body: dict[str, Any],
    headers: dict[str, str],
) -> httpx.Response:
    last: BaseException | None = None
    for attempt in range(3):
        try:
            return await client.post(url, json=json_body, headers=headers)
        except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last = e
            await asyncio.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"OpenRouter connection failed after retries: {last!r}") from last


async def _extract_openrouter(image_bytes: bytes, mime: str) -> ExtractionResult:
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set; configure it in the environment to run extraction."
        )
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    payload: dict[str, Any] = {
        "temperature": 0,
        "max_tokens": 8192,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "First extract form_header (state, lga, ward, pu_name, pu_code, election_type), then party and summary figures and in-words fields. Reply with JSON only.",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": settings.PUBLIC_BASE_URL,
        "X-Title": "AuditNigeria",
    }

    primary = settings.OPENROUTER_MODEL.strip()
    models: list[str] = []
    for m in (primary, *_OPENROUTER_MODEL_FALLBACKS):
        if m and m not in models:
            models.append(m)

    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    last_no_endpoint: str | None = None
    body: dict[str, Any] | None = None
    used_model: str | None = None

    async with httpx.AsyncClient(timeout=180.0) as client:
        for model in models:
            payload["model"] = model
            r = await _post_with_retries(client, url, json_body=payload, headers=headers)
            txt = r.text or ""
            if r.status_code == 404 and "No endpoints" in txt:
                last_no_endpoint = f"{model}: {txt[:1500]}"
                continue
            if r.status_code >= 400:
                snippet = txt[:4000]
                raise RuntimeError(
                    f"OpenRouter HTTP {r.status_code} for model={model!r}: {snippet}"
                )
            body = r.json()
            break
        else:
            raise RuntimeError(
                "No OpenRouter model with available providers. Tried: "
                f"{models!r}. Last 404 detail: {last_no_endpoint}"
            )

    assert body is not None
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected OpenRouter response: {body!r}") from e
    if isinstance(content, list):
        text_parts = [c.get("text", "") for c in content if isinstance(c, dict)]
        content = "".join(text_parts)
    if not isinstance(content, str):
        raise RuntimeError(f"Unexpected message content type: {type(content)}")
    data = _parse_extraction_json(content)
    return ExtractionResult.model_validate(data)


async def _extract_bedrock(image_bytes: bytes, mime: str) -> ExtractionResult:
    raise RuntimeError(
        "AWS Bedrock path is not wired in this MVP; set USE_AWS_BEDROCK=false and use OpenRouter."
    )


def extraction_to_consensus_dict(result: ExtractionResult) -> dict[str, Any]:
    from app.services.number_words import (
        figures_words_party_mismatches,
        figures_words_summary_mismatches,
    )

    party_mm = figures_words_party_mismatches(
        result.party_results, result.party_in_words
    )
    summary_mm = figures_words_summary_mismatches(
        result.summary, result.summary_in_words
    )
    return {
        "form_header": result.form_header.model_dump(),
        "party_results": dict(result.party_results),
        "party_in_words": dict(result.party_in_words),
        "summary": dict(result.summary),
        "summary_in_words": dict(result.summary_in_words),
        "is_math_correct": result.is_math_correct,
        "figures_words_verification": {
            "party_mismatches": party_mm,
            "summary_mismatches": summary_mm,
            "all_ok": len(party_mm) == 0 and len(summary_mm) == 0,
        },
    }
