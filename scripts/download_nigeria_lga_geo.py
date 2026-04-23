#!/usr/bin/env python3
"""
Download Nigeria LGA (ADM2) boundaries GeoJSON from the World Bank open catalog
(mirror of OCHA / HDX) and emit a small centroids file for map markers.

Source dataset: "Nigeria - Administrative Boundaries" (CC-BY-4.0)
  https://energydata.info/dataset/nigeria-administrative-boundaries-2017
Direct resource (LGA GeoJSON):
  https://datacatalogfiles.worldbank.org/ddh-published/0039368/1/DR0048906/ngaadmbndaadm2osgof20170222.geojson

Run from repo root:
  python scripts/download_nigeria_lga_geo.py

Requires: Python 3.10+ (stdlib only).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from json import JSONDecoder
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "geo" / "raw"
RAW_FILE = RAW_DIR / "nga-lga-admin2-osgof-20170222.geojson"
OUT_FILE = REPO_ROOT / "frontend" / "public" / "geo" / "nigeria-lga-centroids.json"
SOURCE_URL = (
    "https://datacatalogfiles.worldbank.org/ddh-published/0039368/1/"
    "DR0048906/ngaadmbndaadm2osgof20170222.geojson"
)


def ring_centroid(ring: list) -> tuple[float, float, float]:
    """Return (abs_area, cx, cy) for a closed or open lon/lat ring (EPSG:4326)."""
    pts = ring
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    if n == 0:
        return 0.0, 0.0, 0.0
    if n < 3:
        return 0.0, sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    twice_a = 0.0
    cx_n = 0.0
    cy_n = 0.0
    for i in range(n):
        j = (i + 1) % n
        xi, yi = float(pts[i][0]), float(pts[i][1])
        xj, yj = float(pts[j][0]), float(pts[j][1])
        cross = xi * yj - xj * yi
        twice_a += cross
        cx_n += (xi + xj) * cross
        cy_n += (yi + yj) * cross
    if abs(twice_a) < 1e-30:
        return 0.0, sum(float(p[0]) for p in pts) / n, sum(float(p[1]) for p in pts) / n
    cx = cx_n / (3.0 * twice_a)
    cy = cy_n / (3.0 * twice_a)
    return abs(twice_a) / 2.0, cx, cy


def multipolygon_centroid(coords: list) -> tuple[float, float]:
    """GeoJSON MultiPolygon coordinates -> approximate centroid (weighted by ring area)."""
    total_a = 0.0
    wx = 0.0
    wy = 0.0
    for polygon in coords:
        if not polygon:
            continue
        exterior = polygon[0]
        a, cx, cy = ring_centroid(exterior)
        if a <= 0:
            continue
        total_a += a
        wx += cx * a
        wy += cy * a
    if total_a <= 0:
        # Fallback: mean of first exterior vertices
        flat: list[tuple[float, float]] = []
        for polygon in coords:
            if polygon and polygon[0]:
                flat.extend((float(x), float(y)) for x, y in polygon[0][:50])
        if not flat:
            return 0.0, 0.0
        return sum(p[0] for p in flat) / len(flat), sum(p[1] for p in flat) / len(flat)
    return wx / total_a, wy / total_a


def geometry_centroid(geom: dict) -> tuple[float, float]:
    t = geom.get("type")
    c = geom.get("coordinates")
    if not t or c is None:
        return 0.0, 0.0
    if t == "Polygon":
        return multipolygon_centroid([c])
    if t == "MultiPolygon":
        return multipolygon_centroid(c)
    return 0.0, 0.0


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading:\n  {url}\n-> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "audit-nigeria-mvp-geo-script/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    # Some mirrors append non-JSON text; persist only the first JSON value.
    try:
        text = data.decode("utf-8")
        obj, _end = JSONDecoder().raw_decode(text)
        data = (json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    dest.write_bytes(data)
    print(f"Saved {len(data) / 1024 / 1024:.2f} MiB (sanitized if needed)")


def main() -> int:
    if "--help" in sys.argv:
        print(__doc__)
        return 0
    if not RAW_FILE.exists() or "--force-download" in sys.argv:
        download(SOURCE_URL, RAW_FILE)
    else:
        print(f"Using existing raw file (pass --force-download to re-fetch):\n  {RAW_FILE}")

    text = RAW_FILE.read_text(encoding="utf-8")
    fc, _end = JSONDecoder().raw_decode(text)
    features = fc.get("features") or []
    records: list[dict] = []

    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        state = props.get("admin1Name") or ""
        lga = props.get("admin2Name") or ""
        pcod = props.get("admin2Pcod") or ""
        lng, lat = geometry_centroid(geom)
        if not state or not lga:
            continue
        row = {
            "stateName": state,
            "lgaName": lga,
            "admin2Pcod": pcod,
            "lng": round(lng, 6),
            "lat": round(lat, 6),
        }
        records.append(row)

    payload = {
        "version": 1,
        "sourceName": "Nigeria - Administrative Boundaries (OCHA via World Bank)",
        "sourceUrl": "https://energydata.info/dataset/nigeria-administrative-boundaries-2017",
        "geojsonUrl": SOURCE_URL,
        "license": "CC-BY-4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "note": (
            "Centroids are derived from polygon geometry (planar lon/lat — fine for marker placement). "
            "Join to app LGA rows by state_name + lga_name (case-insensitive); admin2Pcod is stable if you "
            "add a DB column later."
        ),
        "featureCount": len(records),
        "records": records,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} LGA centroids -> {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
