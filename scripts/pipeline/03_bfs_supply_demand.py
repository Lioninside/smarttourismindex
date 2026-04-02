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
TARGET_YEAR  = "2025"
# No TARGET_MONTH — file has only individual months (German names); we sum/average per commune.
# Column names are German: Jahr, Monat, Gemeinde, Betriebe, Zimmer, Betten,
#   Ankünfte, Logiernächte, Zimmernächte, Zimmerauslastung in %, Bettenauslastung in %


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


def main() -> None:
    if not PLACE_MAPPING.exists():
        raise FileNotFoundError(f"Missing place mapping file: {PLACE_MAPPING}")

    mapping = load_place_mapping(PLACE_MAPPING)

    # Accumulate annual totals per commune across all monthly rows.
    # Flow metrics (arrivals, overnights, room nights): sum.
    # Stock metrics (establishments, rooms, beds): average across months.
    # Occupancy %: average across months.
    totals: Dict[str, Dict[str, Any]] = {}
    unmapped_communes: set = set()

    with RAW_CSV.open("r", encoding=CSV_ENCODING, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("Jahr") != TARGET_YEAR:
                continue
            commune = (row.get("Gemeinde") or "").strip()
            if not commune:
                continue
            if commune not in mapping:
                unmapped_communes.add(commune)
                continue
            if commune not in totals:
                totals[commune] = {
                    "establishments_sum": 0, "rooms_sum": 0, "beds_sum": 0,
                    "arrivals": 0, "overnight_stays": 0, "room_nights": 0,
                    "room_occ_sum": 0.0, "bed_occ_sum": 0.0, "n_months": 0,
                }
            t = totals[commune]
            t["n_months"]          += 1
            t["establishments_sum"] += to_int(row.get("Betriebe", "0"))
            t["rooms_sum"]          += to_int(row.get("Zimmer", "0"))
            t["beds_sum"]           += to_int(row.get("Betten", "0"))
            t["arrivals"]           += to_int(row.get("Ankünfte", "0"))
            t["overnight_stays"]    += to_int(row.get("Logiernächte", "0"))
            t["room_nights"]        += to_int(row.get("Zimmernächte", "0"))
            t["room_occ_sum"]       += to_float(row.get("Zimmerauslastung in %", "0"))
            t["bed_occ_sum"]        += to_float(row.get("Bettenauslastung in %", "0"))

    normalized: List[Dict[str, Any]] = []
    for commune, t in totals.items():
        place = mapping.get(commune)
        if not place or not place.get("active", False):
            continue
        n = t["n_months"] if t["n_months"] > 0 else 1
        normalized.append({
            "slug":           place["slug"],
            "commune_bfs":    commune,
            "year":           int(TARGET_YEAR),
            "establishments": round(t["establishments_sum"] / n),
            "rooms":          round(t["rooms_sum"] / n),
            "beds":           round(t["beds_sum"] / n),
            "arrivals":       t["arrivals"],
            "overnight_stays": t["overnight_stays"],
            "room_nights":    t["room_nights"],
            "room_occupancy": round(t["room_occ_sum"] / n, 1),
            "bed_occupancy":  round(t["bed_occ_sum"] / n, 1),
        })

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