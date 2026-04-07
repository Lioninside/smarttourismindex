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

Water signal used for scoring (water_equivalent_m2):
  - Lakes: clipped polygon area in m²  (Lake Thun next to Spiez >> small pond)
  - Rivers: clipped line length × RIVER_WIDTH_M to convert to equivalent m²
    (Aare through Bern, Rhine through Basel contribute significant area;
     small alpine streams contribute modestly but not enough to dominate)
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

# Assumed average river/stream width for area conversion.
# A major river like the Aare/Rhine is ~60-100m wide; smaller streams are 5-20m.
# 30m is a reasonable mid-point that gives rivers meaningful weight without
# making every small stream dominate the score.
RIVER_WIDTH_M = 30.0

SPOT_CHECK_SLUGS = [
    # Lakeside towns — should score high on lake area
    "spiez", "beckenried", "vitznau", "weggis", "kussnacht", "bourg-en-lavaux",
    # River cities — should score well via river length
    "bern", "basel", "thun",
    # Inland towns with limited water — should score low
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


def water_label(local_equiv_m2: float, nearby_equiv_m2: float) -> str:
    if local_equiv_m2 > 0:
        return "local"
    if nearby_equiv_m2 > 0:
        return "reachable"
    return "limited"


def _water_equivalent_m2(features: gpd.GeoDataFrame, buf) -> float:
    """Combined water area equivalent within buffer (m²).

    Lakes: clipped polygon area.
    Rivers/streams: clipped line length × RIVER_WIDTH_M.

    This treats a major river crossing the buffer (e.g. Aare through Bern,
    Rhine through Basel) as a meaningful water asset comparable in scale to
    a medium-sized lake, while keeping small alpine streams at modest values.
    """
    if features.empty:
        return 0.0

    lakes   = features[features["water_type"] == "standing"]
    rivers  = features[features["water_type"] == "flowing"]

    lake_area = 0.0
    if not lakes.empty:
        lake_area = float(lakes.geometry.intersection(buf).area.sum())

    river_area = 0.0
    if not rivers.empty:
        river_area = float(rivers.geometry.intersection(buf).length.sum()) * RIVER_WIDTH_M

    return lake_area + river_area


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

        local_equiv_m2  = _water_equivalent_m2(local,  buf_local)
        nearby_equiv_m2 = _water_equivalent_m2(nearby, buf_nearby)

        rows.append(
            {
                "slug": place["slug"],
                "name": place["name"],
                "water_features_2km":    int(len(local)),
                "water_features_10km":   int(len(nearby)),
                "water_equiv_2km_m2":    round(local_equiv_m2),
                "water_equiv_10km_m2":   round(nearby_equiv_m2),
                "local_water":           bool(local_equiv_m2 > 0),
                "reachable_water":       bool(nearby_equiv_m2 > 0),
                "water_access_label":    water_label(local_equiv_m2, nearby_equiv_m2),
            }
        )

    rows.sort(key=lambda x: x["slug"])
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    print(f"  Local buffer: {BUFFER_LOCAL_M}m  |  Nearby buffer: {BUFFER_NEARBY_M}m")
    print(f"  River width assumption: {RIVER_WIDTH_M}m")
    _spot_check(rows)


def _spot_check(rows: List[Dict[str, Any]]) -> None:
    by_slug = {r["slug"]: r for r in rows}
    print("\nWATER SPOT-CHECK:")
    for slug in SPOT_CHECK_SLUGS:
        r = by_slug.get(slug)
        if r is None:
            print(f"  {slug:<28} — not in places list")
            continue
        equiv_ha = r.get("water_equiv_2km_m2", 0) / 10_000
        print(f"  {slug:<28} equiv_ha={equiv_ha:>8.1f}  "
              f"local={str(r['local_water']):<5}  label={r['water_access_label']}")


if __name__ == "__main__":
    main()
