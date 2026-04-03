#!/usr/bin/env python3
"""
09_heritage.py

Match each place to the ISOS national heritage inventory.

Input:
  - metadata/places_master.csv
  - data_raw/isos/isos_national.geojson  (EPSG:2056 LV95 points, ~1255 features)

Output:
  - data_processed/heritage/heritage_metrics.json

Scoring:
  For each place, find any ISOS settlement centroid within 2 km (Euclidean in EPSG:2056).
  Apply graded heritage_score based on siedlungskategorie.
  If multiple ISOS entries within 2 km, take the highest score.
  No match -> heritage_score = 0.0

Note: swiss_unesco_sites.json is no longer used.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pyproj import Transformer

# Place coordinates (WGS84) → LV95 for metre-based distance matching
_WGS84_TO_LV95 = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)

PLACES_CSV   = Path("metadata/places_master.csv")
ISOS_GEOJSON = Path("data_raw/isos/isos_national.geojson")
OUTPUT_JSON  = Path("data_processed/heritage/heritage_metrics.json")

BUFFER_M = 2000  # 2 km exact in metres (Euclidean in LV95)

# Graded scores per siedlungskategorie (case-insensitive key lookup)
ISOS_SCORES: Dict[str, float] = {
    "stadt":               1.0,
    "kleinstadt/flecken":  1.0,
    "städtische gemeinde": 1.0,
    "dorf":                0.7,
    "verstädtertes dorf":  0.7,
    "villaggio":           0.7,
    "village":             0.7,
    "spezialfall":         0.4,
    "cas particulier":     0.4,
    "sonderfall":          0.4,
    "agglomeration":       0.4,
}
ISOS_DEFAULT_SCORE = 0.5  # any unrecognised category


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if str(row.get("active", "")).strip().lower() != "true":
                continue
            lat = float(row["lat"])
            lon = float(row["lon"])
            # Convert WGS84 → LV95 for metre-based spatial matching
            e, n = _WGS84_TO_LV95.transform(lon, lat)
            rows.append({
                "slug": row["slug"].strip(),
                "name": row["name"].strip(),
                "e": e,
                "n": n,
            })
        return rows


def load_isos(path: Path) -> List[Dict[str, Any]]:
    """Load ISOS GeoJSON. Coordinates are LV95 (E, N) — keep as-is, no reprojection."""
    with path.open("r", encoding="utf-8-sig") as f:   # utf-8-sig strips BOM if present
        fc = json.load(f)

    entries = []
    for feat in fc.get("features", []):
        geom  = feat.get("geometry") or {}
        props = feat.get("properties") or {}

        if geom.get("type") != "Point":
            continue

        # Coordinates are already LV95 (E, N) — use directly
        e, n = geom["coordinates"][0], geom["coordinates"][1]

        # Try common field names for settlement category
        kategorie = (
            props.get("siedlungskategorie")
            or props.get("kategorie")
            or props.get("KATEGORIE")
            or props.get("type")
            or ""
        ).strip()

        name = (
            props.get("name")
            or props.get("NAME")
            or props.get("ortsname")
            or ""
        ).strip()

        entries.append({"e": e, "n": n, "name": name, "kategorie": kategorie})

    return entries


def isos_score(kategorie: str) -> float:
    return ISOS_SCORES.get(kategorie.lower(), ISOS_DEFAULT_SCORE)


def best_isos_match(
    place_e: float,
    place_n: float,
    isos_entries: List[Dict[str, Any]],
) -> Optional[Tuple[str, str, float]]:
    """Return (name, kategorie, score) of the best ISOS match within BUFFER_M, or None."""
    best_dist  = BUFFER_M + 1
    best_score = -1.0
    best_entry: Optional[Dict[str, Any]] = None

    for entry in isos_entries:
        dist = math.sqrt((place_e - entry["e"]) ** 2 + (place_n - entry["n"]) ** 2)
        if dist > BUFFER_M:
            continue
        score = isos_score(entry["kategorie"])
        # Prefer highest score; break ties by distance
        if score > best_score or (score == best_score and dist < best_dist):
            best_score = score
            best_dist  = dist
            best_entry = entry

    if best_entry is None:
        return None
    return best_entry["name"], best_entry["kategorie"], best_score


def main() -> None:
    for p in [PLACES_CSV, ISOS_GEOJSON]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places       = read_places(PLACES_CSV)
    isos_entries = load_isos(ISOS_GEOJSON)
    print(f"  Loaded {len(isos_entries)} ISOS entries")

    rows: List[Dict[str, Any]] = []
    matched = 0
    for place in places:
        match = best_isos_match(place["e"], place["n"], isos_entries)
        if match:
            isos_name, isos_kat, score = match
            matched += 1
        else:
            isos_name, isos_kat, score = "", "", 0.0

        rows.append({
            "slug":           place["slug"],
            "name":           place["name"],
            "isos_name":      isos_name,
            "isos_kategorie": isos_kat,
            "heritage_score": round(score, 4),
        })

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows ({matched} ISOS matches)")
    _spot_check(rows)


# Spot-check: (slug, expect_match, expected_kategorie_contains)
# expect_match=True → should have an isos_name; False → should be empty
_SPOT_CHECK = [
    ("bellinzona",   True,  "kleinstadt"),
    ("murten",       True,  "kleinstadt"),
    ("gruyeres",     True,  "dorf"),
    ("schaffhausen", True,  "stadt"),
    ("appenzell",    True,  "dorf"),
    ("dubendorf",    False, ""),
    ("koniz",        False, ""),
    ("lancy",        False, ""),
]


def _spot_check(rows: List[Dict[str, Any]]) -> None:
    by_slug = {r["slug"]: r for r in rows}
    print("\nHERITAGE SPOT-CHECK:")
    for slug, expect_match, kat_fragment in _SPOT_CHECK:
        r = by_slug.get(slug)
        if r is None:
            print(f"  {slug:<14}: not in places list — skipped")
            continue
        isos_name = r.get("isos_name", "")
        isos_kat  = r.get("isos_kategorie", "")
        score     = r.get("heritage_score", 0.0)
        has_match = bool(isos_name)
        if expect_match:
            ok = has_match and kat_fragment.lower() in isos_kat.lower()
            isos_str = f"{isos_name} ({isos_kat})"
        else:
            ok = not has_match
            isos_str = "—"
        mark = "✓" if ok else "✗"
        suffix = "  (expected)" if not expect_match else ""
        print(f"  {slug:<14}: score={score:.1f}  isos={isos_str}{suffix}  {mark}")


if __name__ == "__main__":
    main()
