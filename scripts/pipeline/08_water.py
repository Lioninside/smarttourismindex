#!/usr/bin/env python3
"""
08_water.py

Reads the swissTLM3D File Geodatabase and exports place-level water metrics.

Expected input:
  - places_master.csv
  - data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb

Output:
  - data_processed/water/water_metrics.json
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

PLACES_CSV = Path("metadata/places_master.csv")
GDB_PATH = Path("data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb")
OUTPUT_JSON = Path("data_processed/water/water_metrics.json")

FLOWING_LAYER = "TLM_FLIESSGEWAESSER"
STANDING_LAYER = "TLM_STEHENDES_GEWAESSER"


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


def read_water() -> gpd.GeoDataFrame:
    if not GDB_PATH.exists():
        raise FileNotFoundError(f"Missing GDB: {GDB_PATH}")

    flowing = gpd.read_file(GDB_PATH, layer=FLOWING_LAYER)
    standing = gpd.read_file(GDB_PATH, layer=STANDING_LAYER)

    if flowing.crs is None or standing.crs is None:
        raise ValueError("One of the water layers has no CRS")

    flowing = flowing.to_crs(2056)
    standing = standing.to_crs(2056)

    flowing["water_type"] = "flowing"
    standing["water_type"] = "standing"

    return gpd.GeoDataFrame(
        pd.concat([flowing, standing], ignore_index=True),
        geometry="geometry",
        crs=2056,
    )


def water_label(local_count: int, nearby_count: int) -> str:
    if local_count > 0:
        return "local"
    if nearby_count > 0:
        return "reachable"
    return "limited"


def main() -> None:
    places = read_places(PLACES_CSV)
    water = read_water()

    rows: List[Dict[str, Any]] = []
    for place in places:
        point = gpd.GeoSeries([Point(place["lon"], place["lat"])], crs=4326).to_crs(2056).iloc[0]
        buf2 = point.buffer(2000)
        buf10 = point.buffer(10000)

        local = water[water.intersects(buf2)]
        nearby = water[water.intersects(buf10)]

        rows.append(
            {
                "slug": place["slug"],
                "name": place["name"],
                "water_features_2km": int(len(local)),
                "water_features_10km": int(len(nearby)),
                "local_water": bool(len(local) > 0),
                "reachable_water": bool(len(nearby) > 0),
                "water_access_label": water_label(len(local), len(nearby)),
            }
        )

    rows.sort(key=lambda x: x["slug"])
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()