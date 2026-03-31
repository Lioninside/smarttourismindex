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
  For each place, find any ISOS settlement centroid within 2 km (haversine).
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

# ISOS GeoJSON coordinates are in LV95 (EPSG:2056) — reproject to WGS84
_LV95_TO_WGS84 = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)

PLACES_CSV   = Path("metadata/places_master.csv")
ISOS_GEOJSON = Path("data_raw/isos/isos_national.geojson")
OUTPUT_JSON  = Path("data_processed/heritage/heritage_metrics.json")

MATCH_RADIUS_KM = 2.0

# Graded scores per siedlungskategorie (case-insensitive key lookup)
ISOS_SCORES: Dict[str, float] = {
    "stadt":              1.0,
    "kleinstadt/flecken": 1.0,
    "dorf":               0.7,
    "spezialfall":        0.4,
    "cas particulier":    0.4,
    "villaggio":          0.7,
    "village":            0.7,
    "sonderfall":         0.4,
}
ISOS_DEFAULT_SCORE = 0.5  # any unrecognised category


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if str(row.get("active", "")).strip().lower() != "true":
                continue
            rows.append({
                "slug": row["slug"].strip(),
                "name": row["name"].strip(),
                "lat":  float(row["lat"]),
                "lon":  float(row["lon"]),
            })
        return rows


def load_isos(path: Path) -> List[Dict[str, Any]]:
    """Load ISOS GeoJSON, return list of {lat, lon, name, kategorie}."""
    with path.open("r", encoding="utf-8") as f:
        fc = json.load(f)

    entries = []
    for feat in fc.get("features", []):
        geom  = feat.get("geometry") or {}
        props = feat.get("properties") or {}

        if geom.get("type") != "Point":
            continue

        # Coordinates are LV95 (E, N) — convert to WGS84 (lon, lat)
        lon, lat = _LV95_TO_WGS84.transform(geom["coordinates"][0], geom["coordinates"][1])

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

        entries.append({"lat": lat, "lon": lon, "name": name, "kategorie": kategorie})

    return entries


def isos_score(kategorie: str) -> float:
    return ISOS_SCORES.get(kategorie.lower(), ISOS_DEFAULT_SCORE)


def best_isos_match(
    place_lat: float,
    place_lon: float,
    isos_entries: List[Dict[str, Any]],
) -> Optional[Tuple[str, str, float]]:
    """Return (name, kategorie, score) of the best ISOS match within radius, or None."""
    best_dist  = MATCH_RADIUS_KM + 1
    best_score = -1.0
    best_entry: Optional[Dict[str, Any]] = None

    for entry in isos_entries:
        dist = haversine_km(place_lat, place_lon, entry["lat"], entry["lon"])
        if dist > MATCH_RADIUS_KM:
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
        match = best_isos_match(place["lat"], place["lon"], isos_entries)
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


if __name__ == "__main__":
    main()
