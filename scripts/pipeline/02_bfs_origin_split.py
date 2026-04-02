#!/usr/bin/env python3
"""
02_bfs_origin_split.py

Reads the BFS commune-level guest-origin CSV and exports a normalized JSON file
with domestic vs international demand metrics per place.

Input:
  - data_raw/bfs/px-x-1003020000_101_*.csv  (overnights/arrivals by origin)
  - metadata/place_mapping.json

Output:
  - data_processed/bfs/bfs_origin_split_2025.json
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

_BFS_DIR = Path("data_raw/bfs")
_matches = sorted(_BFS_DIR.glob("px-x-1003020000_101_*.csv"))
if not _matches:
    raise FileNotFoundError("No px-x-1003020000_101_*.csv found in data_raw/bfs/")
RAW_CSV = _matches[-1]
PLACE_MAPPING = Path("metadata/place_mapping.json")
OUTPUT_JSON   = Path("data_processed/bfs/bfs_origin_split_2025.json")

VERSION      = "2.0.0"   # monthly aggregation, no TARGET_MONTH filter
CSV_ENCODING = "ISO-8859-1"
TARGET_YEAR  = "2025"
# No TARGET_MONTH — file has only individual months; we sum all 12 per commune.


def load_place_mapping(path: Path) -> Dict[str, Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def to_int(value: str) -> int:
    value = (value or "").strip()
    if not value or value in {"...", "-", "nan", "NaN"}:
        return 0
    cleaned = value.replace("'", "").replace(" ", "").replace(",", ".")
    return int(float(cleaned))


def safe_share(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


def main() -> None:
    print(f"  02_bfs_origin_split v{VERSION}  file={RAW_CSV.name}  year={TARGET_YEAR}")

    if not PLACE_MAPPING.exists():
        raise FileNotFoundError(f"Missing place mapping file: {PLACE_MAPPING}")

    mapping = load_place_mapping(PLACE_MAPPING)
    print(f"  Mapping: {len(mapping)} communes loaded")

    # Accumulate annual totals per commune across all monthly rows
    totals: Dict[str, Dict[str, int]] = {}
    unmapped_communes: set = set()
    rows_read = 0
    rows_year_match = 0

    with RAW_CSV.open("r", encoding=CSV_ENCODING, newline="") as f:
        for row in csv.DictReader(f):
            rows_read += 1
            if row.get("Year") != TARGET_YEAR:
                continue
            rows_year_match += 1
            commune = (row.get("Commune") or "").strip()
            if not commune:
                continue
            if commune not in mapping:
                unmapped_communes.add(commune)
                continue
            if commune not in totals:
                totals[commune] = {
                    "total_arrivals": 0, "total_overnight_stays": 0,
                    "domestic_arrivals": 0, "domestic_overnight_stays": 0,
                }
            t = totals[commune]
            t["total_arrivals"]          += to_int(row.get("Visitors' country of residence - total Arrivals", "0"))
            t["total_overnight_stays"]   += to_int(row.get("Visitors' country of residence - total Overnight stays", "0"))
            t["domestic_arrivals"]       += to_int(row.get("Switzerland Arrivals", "0"))
            t["domestic_overnight_stays"] += to_int(row.get("Switzerland Overnight stays", "0"))

    print(f"  Rows read: {rows_read}  matched year={TARGET_YEAR}: {rows_year_match}  communes accumulated: {len(totals)}")

    normalized: List[Dict[str, Any]] = []
    for commune, t in totals.items():
        place = mapping.get(commune)
        if not place or not place.get("active", False):
            continue
        ta  = t["total_arrivals"]
        to_ = t["total_overnight_stays"]
        da  = t["domestic_arrivals"]
        do_ = t["domestic_overnight_stays"]
        ia  = max(ta - da, 0)
        io_ = max(to_ - do_, 0)
        normalized.append({
            "slug":                            place["slug"],
            "commune_bfs":                     commune,
            "year":                            int(TARGET_YEAR),
            "total_arrivals":                  ta,
            "total_overnight_stays":           to_,
            "domestic_arrivals":               da,
            "domestic_overnight_stays":        do_,
            "international_arrivals":          ia,
            "international_overnight_stays":   io_,
            "domestic_share_arrivals":         safe_share(da,  ta),
            "domestic_share_overnights":       safe_share(do_, to_),
            "international_share_arrivals":    safe_share(ia,  ta),
            "international_share_overnights":  safe_share(io_, to_),
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