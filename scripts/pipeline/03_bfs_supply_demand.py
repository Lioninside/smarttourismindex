#!/usr/bin/env python3
"""
03_bfs_supply_demand.py

Reads the BFS commune-level hotel supply/demand CSV and exports a normalized JSON file
with accommodation, demand, and occupancy metrics per place.

Input:
  - data_raw/bfs/px-x-1003020000_201_*.csv  (supply/demand by commune)
  - metadata/place_mapping.json

Output:
  - data_processed/bfs/bfs_supply_demand_2025.json
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

_BFS_DIR = Path("data_raw/bfs")
_matches = sorted(_BFS_DIR.glob("px-x-1003020000_201_*.csv"))
if not _matches:
    raise FileNotFoundError("No px-x-1003020000_201_*.csv found in data_raw/bfs/")
RAW_CSV = _matches[-1]
print(f"  Using: {RAW_CSV.name}")
PLACE_MAPPING = Path("metadata/place_mapping.json")
OUTPUT_JSON = Path("data_processed/bfs/bfs_supply_demand_2025.json")

CSV_ENCODING = "ISO-8859-1"
TARGET_YEAR = "2025"
TARGET_MONTH = "Total of the year"


def load_place_mapping(path: Path) -> Dict[str, Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def to_int(value: str) -> int:
    value = (value or "").strip()
    if not value or value in {"...", "-", "nan", "NaN"}:
        return 0
    cleaned = value.replace("'", "").replace(" ", "").replace(",", ".")
    return int(float(cleaned))


def to_float(value: str) -> float:
    value = (value or "").strip()
    if not value or value in {"...", "-", "nan", "NaN"}:
        return 0.0
    cleaned = value.replace("'", "").replace(" ", "").replace(",", ".")
    return round(float(cleaned), 2)


def normalize_row(row: Dict[str, str], mapping: Dict[str, Dict[str, Any]]) -> Dict[str, Any] | None:
    if row.get("Year") != TARGET_YEAR:
        return None
    if row.get("Month") != TARGET_MONTH:
        return None

    commune_bfs = (row.get("Commune") or "").strip()
    if not commune_bfs:
        return None

    place = mapping.get(commune_bfs)
    if not place or not place.get("active", False):
        return None

    return {
        "slug": place["slug"],
        "commune_bfs": commune_bfs,
        "year": int(TARGET_YEAR),
        "establishments": to_int(row.get("Establishments", "0")),
        "rooms": to_int(row.get("Rooms", "0")),
        "beds": to_int(row.get("Beds", "0")),
        "arrivals": to_int(row.get("Arrivals", "0")),
        "overnight_stays": to_int(row.get("Overnight stays", "0")),
        "room_nights": to_int(row.get("Room nights", "0")),
        "room_occupancy": to_float(row.get("Room occupancy", "0")),
        "bed_occupancy": to_float(row.get("Bed occupancy", "0")),
    }


def main() -> None:
    if not PLACE_MAPPING.exists():
        raise FileNotFoundError(f"Missing place mapping file: {PLACE_MAPPING}")

    mapping = load_place_mapping(PLACE_MAPPING)

    normalized: List[Dict[str, Any]] = []
    unmapped_communes = set()

    with RAW_CSV.open("r", encoding=CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            commune_bfs = (row.get("Commune") or "").strip()
            if commune_bfs and commune_bfs not in mapping:
                unmapped_communes.add(commune_bfs)

            normalized_row = normalize_row(row, mapping)
            if normalized_row:
                normalized.append(normalized_row)

    normalized.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(normalized)} rows")

    if unmapped_communes:
        print(f"Warning: {len(unmapped_communes)} communes not found in place_mapping.json")
        for commune in sorted(unmapped_communes)[:20]:
            print(f"  - {commune}")
        if len(unmapped_communes) > 20:
            print("  ...")


if __name__ == "__main__":
    main()