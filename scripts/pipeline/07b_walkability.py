#!/usr/bin/env python3
"""
07b_walkability.py

Score each place on pedestrian infrastructure density within 500m.

Input:
  - metadata/places_master.csv
  - data_raw/tlm/tlm_walkability.gpkg  (EPSG:2056)

Output:
  - data_processed/walkability_metrics.json

Columns:
  slug, walkability_path_m (total SHAPE_Length in metres within 500m),
  walkability_score (0–1 min-max normalised across all places)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.geometry import Point

PLACES_CSV      = Path("metadata/places_master.csv")
WALKABILITY_GPKG = Path("data_raw/tlm/tlm_walkability.gpkg")
OUTPUT_JSON     = Path("data_processed/walkability_metrics.json")

BUFFER_M = 500


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
    for p in [PLACES_CSV, WALKABILITY_GPKG]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places = read_places(PLACES_CSV)

    gdf = gpd.read_file(WALKABILITY_GPKG)
    if gdf.crs is None:
        raise ValueError("tlm_walkability.gpkg has no CRS")
    gdf = gdf.to_crs(2056)

    # Ensure geometry length is available
    if "SHAPE_Length" not in gdf.columns:
        gdf["SHAPE_Length"] = gdf.geometry.length

    rows: List[Dict[str, Any]] = []
    for place in places:
        point = gpd.GeoSeries([Point(place["lon"], place["lat"])], crs=4326).to_crs(2056).iloc[0]
        buf = point.buffer(BUFFER_M)
        clipped = gdf[gdf.intersects(buf)]
        total_m = round(float(clipped["SHAPE_Length"].sum()), 1)
        rows.append({
            "slug":               place["slug"],
            "name":               place["name"],
            "walkability_path_m": total_m,
        })

    # Min-max normalise
    vals = [r["walkability_path_m"] for r in rows]
    v_min = min(vals)
    v_max = max(vals)
    v_range = v_max - v_min if v_max > v_min else 1.0

    for r in rows:
        r["walkability_score"] = round((r["walkability_path_m"] - v_min) / v_range, 4)

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    scores = [r["walkability_score"] for r in rows]
    print(f"  walkability_score range: {min(scores):.3f}–{max(scores):.3f}")


if __name__ == "__main__":
    main()
