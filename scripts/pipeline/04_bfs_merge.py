#!/usr/bin/env python3
"""
04_bfs_merge.py

Merges the two normalized BFS outputs into one per-place BFS metrics file.

Inputs:
  - data_processed/bfs/bfs_origin_split_2025.json
  - data_processed/bfs/bfs_supply_demand_2025.json

Output:
  - data_processed/bfs/bfs_place_metrics_2025.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ORIGIN_JSON = Path("data_processed/bfs/bfs_origin_split_2025.json")
SUPPLY_JSON = Path("data_processed/bfs/bfs_supply_demand_2025.json")
OUTPUT_JSON = Path("data_processed/bfs/bfs_place_metrics_2025.json")


def load_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if not ORIGIN_JSON.exists():
        raise FileNotFoundError(f"Missing input JSON: {ORIGIN_JSON}")
    if not SUPPLY_JSON.exists():
        raise FileNotFoundError(f"Missing input JSON: {SUPPLY_JSON}")

    origin_rows = load_json(ORIGIN_JSON)
    supply_rows = load_json(SUPPLY_JSON)

    origin_by_slug = {row["slug"]: row for row in origin_rows}
    supply_by_slug = {row["slug"]: row for row in supply_rows}

    all_slugs = sorted(set(origin_by_slug.keys()) | set(supply_by_slug.keys()))

    merged: List[Dict[str, Any]] = []
    origin_only = []
    supply_only = []

    for slug in all_slugs:
        origin = origin_by_slug.get(slug)
        supply = supply_by_slug.get(slug)

        if origin and not supply:
            origin_only.append(slug)
        if supply and not origin:
            supply_only.append(slug)

        if not origin or not supply:
            # Keep merge strict for now: only export places present in both files
            continue

        merged_row = {
            "slug": slug,
            "commune_bfs": supply.get("commune_bfs") or origin.get("commune_bfs"),
            "year": supply.get("year") or origin.get("year"),

            "establishments": supply["establishments"],
            "rooms": supply["rooms"],
            "beds": supply["beds"],
            "arrivals": supply["arrivals"],
            "overnight_stays": supply["overnight_stays"],
            "room_nights": supply["room_nights"],
            "room_occupancy": supply["room_occupancy"],
            "bed_occupancy": supply["bed_occupancy"],

            "total_arrivals": origin["total_arrivals"],
            "total_overnight_stays": origin["total_overnight_stays"],
            "domestic_arrivals": origin["domestic_arrivals"],
            "domestic_overnight_stays": origin["domestic_overnight_stays"],
            "international_arrivals": origin["international_arrivals"],
            "international_overnight_stays": origin["international_overnight_stays"],
            "domestic_share_arrivals": origin["domestic_share_arrivals"],
            "domestic_share_overnights": origin["domestic_share_overnights"],
            "international_share_arrivals": origin["international_share_arrivals"],
            "international_share_overnights": origin["international_share_overnights"],
        }

        merged.append(merged_row)

    merged.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(merged)} rows")

    if origin_only:
        print(f"Warning: {len(origin_only)} slugs found only in origin split file")
        for slug in origin_only[:20]:
            print(f"  - {slug}")
        if len(origin_only) > 20:
            print("  ...")

    if supply_only:
        print(f"Warning: {len(supply_only)} slugs found only in supply/demand file")
        for slug in supply_only[:20]:
            print(f"  - {slug}")
        if len(supply_only) > 20:
            print("  ...")


if __name__ == "__main__":
    main()
