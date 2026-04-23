"""Generate demo EC8A-style result sheet images (PNG) for testing uploads."""

from __future__ import annotations

import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        p = Path(path)
        if p.is_file():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def generate_sample_sheet_png(
    *,
    variant: int = 0,
    state: str = "Lagos",
    lga: str = "Ikeja",
    pu_name: str = "Demo Polling Unit 001",
    pu_code: str = "DEMO-PU-001",
    width: int = 1200,
    height: int = 1700,
) -> bytes:
    """
    Build a sharp synthetic collation sheet so it passes Laplacian blur checks.
    `variant` seeds pseudo-random vote totals for repeatable demos.
    """
    rng = random.Random(variant)
    parties = [
        ("APC", rng.randint(45, 220)),
        ("PDP", rng.randint(40, 210)),
        ("LP", rng.randint(15, 120)),
        ("NNPP", rng.randint(5, 80)),
        ("ADC", rng.randint(0, 45)),
        ("PRP", rng.randint(0, 30)),
    ]
    parties.sort(key=lambda x: -x[1])

    title_font = _load_font(36)
    header_font = _load_font(24)
    body_font = _load_font(20)
    small_font = _load_font(16)

    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 40

    def text(line: str, font: ImageFont.ImageFont, fill: tuple[int, int, int] = (0, 0, 0)) -> None:
        nonlocal y
        draw.text((48, y), line, font=font, fill=fill)
        y += int(font.size * 1.35) + 4

    text("INDEPENDENT NATIONAL ELECTORAL COMMISSION", title_font)
    text("FORM EC8A (A) — POLLING UNIT LEVEL RESULT (DEMO SHEET)", header_font)
    text("This image is computer-generated for AuditNigeria demos only.", small_font, (90, 90, 90))
    y += 12

    box_top = y
    details = [
        f"State: {state}",
        f"LGA: {lga}",
        f"PU Code: {pu_code}",
        f"PU Name: {pu_name}",
        f"Sheet variant: {variant}",
    ]
    for d in details:
        text(d, body_font)
    box_bottom = y + 8
    draw.rectangle(
        (40, box_top - 8, width - 40, box_bottom),
        outline=(0, 0, 0),
        width=2,
    )
    y = box_bottom + 24

    text("Votes scored by each candidate at this polling unit", header_font)
    y += 8

    col_x = (48, 520, 820, 980)
    row_h = 44

    headers = ("Candidate / Party", "Votes", "Remarks")
    for i, h in enumerate(headers):
        draw.text((col_x[i], y), h, font=body_font, fill=(0, 0, 0))
    y += row_h
    draw.line((40, y, width - 40, y), fill=(0, 0, 0), width=2)
    y += 8

    total = 0
    for party, votes in parties:
        total += votes
        draw.text((col_x[0], y), party, font=body_font)
        draw.text((col_x[1], y), str(votes), font=body_font)
        draw.text((col_x[2], y), "—", font=body_font)
        y += row_h
        draw.line((40, y, width - 40, y), fill=(180, 180, 180), width=1)
        y += 4

    y += 8
    draw.line((40, y, width - 40, y), fill=(0, 0, 0), width=2)
    y += 12
    text(f"Total valid votes (demo): {total}", body_font)
    text("Accredited voters (demo): " + str(total + rng.randint(0, 25)), body_font)
    y += 24

    text("Presiding Officer signature: _________________________", body_font)
    text("Date / Time: _________________________", body_font)
    y += 40

    # High-contrast footer blocks (helps CV / VLM demos)
    for i in range(24):
        x0 = 40 + i * 48
        h = 20 + (i * 7) % 60
        draw.rectangle((x0, y, x0 + 32, y + h), outline=(0, 0, 0), fill=(240 - i * 3, 240 - i * 3, 250))

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=3)
    return buf.getvalue()
