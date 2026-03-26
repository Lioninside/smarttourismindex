#!/usr/bin/env python3
"""
07_hiking.py

Reads swissTLM3D from the File Geodatabase and exports place-level hiking access metrics.

Input:
  - places_master.csv
  - data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb

Output:
  - data_processed/hiking/hiking_metrics.json

MVP logic:
- use TLM_STRASSE
- use WANDERWEGE field when available
- count hiking segments within 5 km and 15 km
- compute total hiking length proxy within 15 km
- create simple hiking access labels
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.geometry import Point

PLACES_CSV = Path("metadata/places_master.csv")
GDB_PATH = Path("data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb")
OUTPUT_JSON = Path("data_processed/hiking/hiking_metrics.json")

HIKING_LAYER = "TLM_STRASSE"


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if str(row.get("active", "")).strip().lower() != "true":
                continue
            rows.append(
                {
                    "slug": row["slug"].strip(),
                    "name": row["name"].strip(),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                }
            )
        return rows


def read_hiking() -> gpd.GeoDataFrame:
    if not GDB_PATH.exists():
        raise FileNotFoundError(f"Missing GDB: {GDB_PATH}")

    gdf = gpd.read_file(GDB_PATH, layer=HIKING_LAYER)

    if gdf.crs is None:
        raise ValueError("Hiking layer has no CRS")

    gdf = gdf.to_crs(2056)

    # Keep only records with hiking classification if field exists
    if "WANDERWEGE" in gdf.columns:
        gdf = gdf[gdf["WANDERWEGE"].notna()]
        # keep all coded hiking trail types (0,1,2) and any string values if present
        allowed_numeric = {0, 1, 2}
        def is_hiking(v: Any) -> bool:
            try:
                return int(v) in allowed_numeric
            except Exception:
                return str(v).strip() != ""
        gdf = gdf[gdf["WANDERWEGE"].apply(is_hiking)]

    return gdf


def label_from_length(length_km_15: float) -> str:
    if length_km_15 >= 150:
        return "excellent"
    if length_km_15 >= 60:
        return "strong"
    if length_km_15 >= 20:
        return "good"
    return "basic"


def main() -> None:
    if not PLACES_CSV.exists():
        raise FileNotFoundError(f"Missing places file: {PLACES_CSV}")

    places = read_places(PLACES_CSV)
    hiking = read_hiking()

    rows: List[Dict[str, Any]] = []
    for place in places:
        point = gpd.GeoSeries([Point(place["lon"], place["lat"])], crs=4326).to_crs(2056).iloc[0]
        buf5 = point.buffer(5000)
        buf15 = point.buffer(15000)

        seg5 = hiking[hiking.intersects(buf5)]
        seg15 = hiking[hiking.intersects(buf15)]

        length_15_km = round(float(seg15.geometry.length.sum()) / 1000.0, 2)

        rows.append(
            {
                "slug": place["slug"],
                "name": place["name"],
                "hiking_segments_5km": int(len(seg5)),
                "hiking_segments_15km": int(len(seg15)),
                "hiking_length_15km_km": length_15_km,
                "hiking_access_label": label_from_length(length_15_km),
                "hiking_reachable": bool(len(seg5) > 0),
            }
        )

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()