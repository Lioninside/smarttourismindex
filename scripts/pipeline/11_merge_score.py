#!/usr/bin/env python3
"""
11_merge_score.py

Merges processed source outputs into one place-level score file.

Inputs:
  - places_master.csv
  - processed JSON files from BFS, climate, GTFS, hiking, water, heritage, OSM

Output:
  - data_processed/final/place_scores.json

MVP logic:
- merge by slug
- create simple normalized component scores
- calculate final weighted score
- expose reachable tags
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

PLACES_CSV = Path("metadata/places_master.csv")
BFS_JSON = Path("data_processed/bfs/bfs_place_metrics_2025.json")
CLIMATE_JSON = Path("data_processed/climate/climate_metrics_jja.json")
GTFS_JSON = Path("data_processed/gtfs/gtfs_access_metrics.json")
HIKING_JSON = Path("data_processed/hiking/hiking_metrics.json")
WATER_JSON = Path("data_processed/water/water_metrics.json")
HERITAGE_JSON = Path("data_processed/heritage/heritage_metrics.json")
OSM_JSON = Path("data_processed/osm/osm_poi_metrics.json")
OUTPUT_JSON = Path("data_processed/final/place_scores.json")


def load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if str(row.get("active", "")).strip().lower() == "true"]


def index_by_slug(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {row["slug"]: row for row in rows if row.get("slug")}


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def main() -> None:
    places = read_places(PLACES_CSV)

    bfs = index_by_slug(load_json(BFS_JSON))
    climate = index_by_slug(load_json(CLIMATE_JSON))
    gtfs = index_by_slug(load_json(GTFS_JSON))
    hiking = index_by_slug(load_json(HIKING_JSON))
    water = index_by_slug(load_json(WATER_JSON))
    heritage = index_by_slug(load_json(HERITAGE_JSON))
    osm = index_by_slug(load_json(OSM_JSON))

    rows: List[Dict[str, Any]] = []

    for place in places:
        slug = place["slug"]
        b = bfs.get(slug, {})
        c = climate.get(slug, {})
        g = gtfs.get(slug, {})
        h = hiking.get(slug, {})
        w = water.get(slug, {})
        he = heritage.get(slug, {})
        o = osm.get(slug, {})

        # Base quality
        base = 0.0
        if he.get("local_unesco"):
            base += 35
        if o.get("museum_count_2km", 0) > 0:
            base += 15
        if o.get("restaurant_count_2km", 0) > 5:
            base += 15
        if w.get("local_water"):
            base += 10
        base += 25  # placeholder walkable-center baseline for MVP

        # Access value
        access = 0.0
        if g.get("anchor_route_count", 0) >= 8:
            access += 35
        elif g.get("anchor_route_count", 0) >= 3:
            access += 20
        if h.get("hiking_reachable"):
            access += 25
        if w.get("reachable_water"):
            access += 15
        if o.get("museum_count_2km", 0) > 0 or he.get("local_unesco"):
            access += 15
        diversity = sum(
            [
                1 if h.get("hiking_reachable") else 0,
                1 if w.get("reachable_water") else 0,
                1 if g.get("anchor_route_count", 0) >= 3 else 0,
                1 if (o.get("museum_count_2km", 0) > 0 or he.get("local_unesco")) else 0,
            ]
        )
        access += 10 if diversity >= 3 else 5 if diversity == 2 else 0

        # Practical comfort
        pt_score = 45 if g.get("pt_strength_label") == "strong" else 30 if g.get("pt_strength_label") == "good" else 15
        temp = c.get("summer_temp_avg", 0)
        precip = c.get("summer_precip_avg", 0)
        sunshine = c.get("summer_sunshine_avg", 0)
        climate_score = 0
        if 15 <= temp <= 24:
            climate_score += 15
        if precip > 0 and precip < 120:
            climate_score += 10
        if sunshine > 0:
            climate_score += 10
        accommodation = 0
        if b.get("beds", 0) >= 200:
            accommodation += 10
        if b.get("establishments", 0) >= 10:
            accommodation += 10
        practical = pt_score + climate_score + accommodation

        # Anti-overtourism
        overnight = b.get("overnight_stays", 0)
        if overnight <= 50000:
            tourism_pressure = 30
        elif overnight <= 150000:
            tourism_pressure = 20
        else:
            tourism_pressure = 10

        total_value_proxy = base + access + practical
        if overnight <= 150000 and total_value_proxy >= 70:
            hiddenness = 50
        elif overnight <= 300000 and total_value_proxy >= 60:
            hiddenness = 35
        else:
            hiddenness = 20

        overtourism_penalty_component = 20 if overnight <= 200000 else 10 if overnight <= 500000 else 0
        anti = hiddenness + tourism_pressure + overtourism_penalty_component

        total = round(
            clamp(base) * 0.25 +
            clamp(access) * 0.35 +
            clamp(practical) * 0.20 +
            clamp(anti) * 0.20,
            2
        )

        reachable_tags = []
        if h.get("hiking_reachable"):
            reachable_tags.append("Hiking")
        if w.get("local_water") or w.get("reachable_water"):
            reachable_tags.append("Water")
        if g.get("anchor_route_count", 0) >= 3:
            reachable_tags.append("Scenic transport")
        if o.get("museum_count_2km", 0) > 0:
            reachable_tags.append("Museums")
        if he.get("local_unesco"):
            reachable_tags.append("UNESCO")

        rows.append(
            {
                "slug": slug,
                "name": place["name"],
                "canton": place.get("canton", ""),
                "score_total": total,
                "subscores": {
                    "base_quality": round(clamp(base), 2),
                    "access_value": round(clamp(access), 2),
                    "practical_comfort": round(clamp(practical), 2),
                    "anti_overtourism": round(clamp(anti), 2),
                },
                "reachable_tags": reachable_tags,
                "metrics": {
                    "overnight_stays": b.get("overnight_stays"),
                    "domestic_share_overnights": b.get("domestic_share_overnights"),
                    "summer_temp_avg": c.get("summer_temp_avg"),
                    "anchor_stop_name": g.get("anchor_stop_name"),
                    "anchor_route_count": g.get("anchor_route_count"),
                    "hiking_length_15km_km": h.get("hiking_length_15km_km"),
                    "museum_count_2km": o.get("museum_count_2km"),
                    "restaurant_count_2km": o.get("restaurant_count_2km"),
                },
                "data_status": {
                    "bfs": bool(b),
                    "climate": bool(c),
                    "gtfs": bool(g),
                    "hiking": bool(h),
                    "water": bool(w),
                    "heritage": bool(he),
                    "osm": bool(o),
                },
            }
        )

    rows.sort(key=lambda x: (-x["score_total"], x["name"]))
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()
