#!/usr/bin/env python3
"""
08_water.py

Reads pre-extracted water GeoPackages and exports place-level water metrics.

Expected input:
  - metadata/places_master.csv
  - data_raw/tlm/tlm_rivers.gpkg   (TLM_FLIESSGEWAESSER, EPSG:2056)
  - data_raw/tlm/tlm_lakes.gpkg    (TLM_STEHENDES_GEWAESSER, EPSG:2056)

Run scripts/tools/ExtractTLM.py first if the GeoPackages don't exist yet.

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

PLACES_CSV   = Path("metadata/places_master.csv")
RIVERS_GPKG  = Path("data_raw/tlm/tlm_rivers.gpkg")
LAKES_GPKG   = Path("data_raw/tlm/tlm_lakes.gpkg")
OUTPUT_JSON  = Path("data_processed/water/water_metrics.json")

BUFFER_LOCAL_M  = 2000   # water within 2km → local_water = True
BUFFER_NEARBY_M = 10000  # water within 10km → reachable_water = True

SPOT_CHECK_SLUGS = [
    # Lakeside towns — should all be local=True
    "spiez", "beckenried", "vitznau", "weggis", "kussnacht", "bourg-en-lavaux",
    # Inland towns — should score low on lakes (rivers may still register)
    "langenthal", "herzogenbuchsee", "wil",
]


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
    for p in (RIVERS_GPKG, LAKES_GPKG):
        if not p.exists():
            raise FileNotFoundError(
                f"Missing: {p}\nRun scripts/tools/ExtractTLM.py first."
            )

    flowing  = gpd.read_file(RIVERS_GPKG)
    standing = gpd.read_file(LAKES_GPKG)

    if flowing.crs is None or standing.crs is None:
        raise ValueError("One of the water GeoPackages has no CRS")

    flowing  = flowing.to_crs(2056)
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
        buf_local  = point.buffer(BUFFER_LOCAL_M)
        buf_nearby = point.buffer(BUFFER_NEARBY_M)

        local  = water[water.intersects(buf_local)]
        nearby = water[water.intersects(buf_nearby)]

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
    print(f"  Local buffer: {BUFFER_LOCAL_M}m  |  Nearby buffer: {BUFFER_NEARBY_M}m")
    _spot_check(rows)


def _spot_check(rows: List[Dict[str, Any]]) -> None:
    by_slug = {r["slug"]: r for r in rows}
    print("\nWATER SPOT-CHECK:")
    for slug in SPOT_CHECK_SLUGS:
        r = by_slug.get(slug)
        if r is None:
            print(f"  {slug:<28} — not in places list")
            continue
        print(f"  {slug:<28} water_2km={r['water_features_2km']:>4}  "
              f"local={str(r['local_water']):<5}  label={r['water_access_label']}")


if __name__ == "__main__":
    main()