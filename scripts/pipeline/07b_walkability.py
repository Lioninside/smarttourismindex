#!/usr/bin/env python3
"""
07b_walkability.py

Score each place on pedestrian-friendly street environment within 3 km.

Source: OSM roads layer (gis_osm_roads_free), features classified as:
  'pedestrian'    — pedestrian zones / Fussgängerzonen (car-free town centres)
  'living_street' — Begegnungszonen / shared zones with pedestrian priority

This replaces the previous TLM_STRASSE_FUSS approach, which systematically
undercounted alpine resort infrastructure because TLM classifies resort
promenades and shared zones as hiking or general paths rather than pedestrian
streets. OSM living_street / pedestrian tags cover these correctly.

Input:
  - metadata/places_master.csv
  - data_raw/osm/osm_switzerland.gpkg  (GeoFabrik free extract)
    OR data_raw/osm/switzerland-latest-free.gpkg

Output:
  - data_processed/walkability_metrics.json

Columns:
  slug, walkability_path_m (total clipped length in metres within 3 km),
  walkability_score (0–1 min-max normalised across all places)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.geometry import Point

PLACES_CSV  = Path("metadata/places_master.csv")
OSM_GPKG_A  = Path("data_raw/osm/osm_switzerland.gpkg")
OSM_GPKG_B  = Path("data_raw/osm/switzerland-latest-free.gpkg")
OUTPUT_JSON = Path("data_processed/walkability_metrics.json")

ROADS_LAYER   = "gis_osm_roads_free"
WALK_FCLASSES = {"pedestrian", "living_street"}

BUFFER_M = 3000

SPOT_CHECK_SLUGS = [
    # Alpine resorts — should now score non-zero (pedestrian zones / living streets)
    "arosa", "davos", "zermatt", "engelberg",
    # Cities — should score highest
    "basel", "bern", "zurich",
    # Small lakeside towns
    "brienz", "spiez",
    # Inland — expect low
    "langenthal", "wil",
]


def find_osm_source() -> Path:
    for p in (OSM_GPKG_A, OSM_GPKG_B):
        if p.exists():
            return p
    raise FileNotFoundError(
        "Missing OSM GeoPackage. Expected one of:\n"
        f"  {OSM_GPKG_A}\n  {OSM_GPKG_B}\n"
        "Download the Switzerland free extract from "
        "https://download.geofabrik.de/europe/switzerland.html"
    )


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


def main() -> None:
    places = read_places(PLACES_CSV)

    src = find_osm_source()
    print(f"Reading OSM roads from {src} ...")
    roads = gpd.read_file(src, layer=ROADS_LAYER)

    if roads.crs is None:
        raise ValueError("OSM roads layer has no CRS")
    if "fclass" not in roads.columns:
        raise ValueError(
            f"Expected 'fclass' column in {ROADS_LAYER}, found: {list(roads.columns)}"
        )

    roads = roads.to_crs(2056)

    walk_roads = roads[roads["fclass"].isin(WALK_FCLASSES)].copy()
    print(f"  {len(walk_roads):,} features with fclass in {WALK_FCLASSES}")

    rows: List[Dict[str, Any]] = []
    for place in places:
        point = (
            gpd.GeoSeries([Point(place["lon"], place["lat"])], crs=4326)
            .to_crs(2056)
            .iloc[0]
        )
        buf = point.buffer(BUFFER_M)

        nearby = walk_roads[walk_roads.intersects(buf)]
        if nearby.empty:
            total_m = 0.0
        else:
            total_m = round(float(nearby.geometry.intersection(buf).length.sum()), 1)

        rows.append({
            "slug":               place["slug"],
            "name":               place["name"],
            "walkability_path_m": total_m,
        })

    # Min-max normalise across all places
    vals    = [r["walkability_path_m"] for r in rows]
    v_min   = min(vals)
    v_max   = max(vals)
    v_range = v_max - v_min if v_max > v_min else 1.0

    for r in rows:
        r["walkability_score"] = round((r["walkability_path_m"] - v_min) / v_range, 4)

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    scores = [r["walkability_score"] for r in rows]
    path_m = [r["walkability_path_m"] for r in rows]
    print(f"  walkability_path_m range: {min(path_m):.0f}–{max(path_m):.0f} m")
    print(f"  walkability_score  range: {min(scores):.3f}–{max(scores):.3f}")
    _spot_check(rows)


def _spot_check(rows: List[Dict[str, Any]]) -> None:
    by_slug = {r["slug"]: r for r in rows}
    print("\nWALKABILITY SPOT-CHECK:")
    for slug in SPOT_CHECK_SLUGS:
        r = by_slug.get(slug)
        if r is None:
            print(f"  {slug:<28} — not in places list")
            continue
        print(
            f"  {slug:<28}  path_m={r['walkability_path_m']:>8.0f}  "
            f"score={r['walkability_score']:.3f}"
        )


if __name__ == "__main__":
    main()
