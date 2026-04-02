#!/usr/bin/env python3
"""
07_hiking.py

Reads swissTLM hiking trails and exports per-place hiking metrics at two radii.

Input:
  - metadata/places_master.csv
  - data_raw/tlm/tlm_hiking.gpkg   (EPSG:2056, marked WANDERWEGE paths)

Output:
  - data_processed/hiking/hiking_metrics.json

Columns:
  local_hiking_m      — trail metres within  4 km (used in Base quality)
  regional_hiking_m   — trail metres within 20 km (used in Access — scenic_access.py)
  hiking_reachable    — bool, any trail within 4 km

Note: prior script read from swissTLM3D GDB. This version reads the pre-exported
tlm_hiking.gpkg which contains only WANDERWEGE-marked paths.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.geometry import Point

PLACES_CSV  = Path("metadata/places_master.csv")
HIKING_GPKG = Path("data_raw/tlm/tlm_hiking.gpkg")
OUTPUT_JSON = Path("data_processed/hiking/hiking_metrics.json")


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


def read_hiking() -> gpd.GeoDataFrame:
    if not HIKING_GPKG.exists():
        raise FileNotFoundError(f"Missing hiking GeoPackage: {HIKING_GPKG}")
    gdf = gpd.read_file(HIKING_GPKG)
    if gdf.crs is None:
        raise ValueError("tlm_hiking.gpkg has no CRS")
    return gdf.to_crs(2056)


def main() -> None:
    if not PLACES_CSV.exists():
        raise FileNotFoundError(f"Missing: {PLACES_CSV}")

    places = read_places(PLACES_CSV)
    hiking = read_hiking()

    rows: List[Dict[str, Any]] = []
    for place in places:
        # Reproject anchor point to LV95 for metre-accurate buffering
        point = gpd.GeoSeries([Point(place["lon"], place["lat"])], crs=4326).to_crs(2056).iloc[0]
        buf4  = point.buffer(4_000)
        buf20 = point.buffer(20_000)

        seg4  = hiking[hiking.intersects(buf4)]
        seg20 = hiking[hiking.intersects(buf20)]

        local_m    = round(float(seg4.geometry.length.sum()), 1)
        regional_m = round(float(seg20.geometry.length.sum()), 1)

        rows.append({
            "slug":              place["slug"],
            "name":              place["name"],
            "local_hiking_m":    local_m,
            "regional_hiking_m": regional_m,
            "hiking_reachable":  bool(len(seg4) > 0),
        })

    # Min-max normalise both hiking metrics
    def minmax(vals: list) -> list:
        v_min = min(vals)
        v_max = max(vals)
        v_range = v_max - v_min if v_max > v_min else 1.0
        return [round((v - v_min) / v_range, 4) for v in vals]

    local_norm    = minmax([r["local_hiking_m"]    for r in rows])
    regional_norm = minmax([r["regional_hiking_m"] for r in rows])
    for i, row in enumerate(rows):
        row["local_hiking_score"]    = local_norm[i]
        row["regional_hiking_score"] = regional_norm[i]

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()
