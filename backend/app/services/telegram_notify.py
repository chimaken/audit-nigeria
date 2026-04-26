"""Optional Telegram notifications (human-in-the-loop alerts)."""

from __future__ import annotations

import logging
from typing import Iterable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _chat_ids() -> list[str]:
    raw = (settings.TELEGRAM_CHAT_IDS or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


async def send_telegram_text(text: str) -> None:
    """Fire-and-forget style: logs failures; does not raise to callers."""
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token or not text.strip():
        return
    ids = _chat_ids()
    if not ids:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload_base = {
        "text": text[:4000],
        "disable_web_page_preview": False,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            for chat_id in ids:
                r = await client.post(url, json={**payload_base, "chat_id": chat_id})
                if r.status_code >= 400:
                    logger.warning(
                        "Telegram sendMessage failed chat_id=%s status=%s body=%s",
                        chat_id,
                        r.status_code,
                        (r.text or "")[:500],
                    )
    except Exception as e:  # noqa: BLE001
        logger.warning("Telegram sendMessage error: %s", e, exc_info=False)
