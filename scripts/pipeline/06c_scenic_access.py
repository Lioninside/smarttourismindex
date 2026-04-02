#!/usr/bin/env python3
"""
06c_scenic_access.py

Score each place on scenic transport and boat services within a 14km radius.

Inputs:
  - metadata/places_master.csv
  - data_raw/tlm/tlm_scenic_transport.gpkg  (EPSG:2056)
  - data_raw/tlm/tlm_boats.gpkg             (EPSG:2056)

Output:
  - data_processed/scenic_access_metrics.json

Columns:
  slug, scenic_transport_count, boat_count, scenic_score (0-1 normalised)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point

PLACES_CSV  = Path("metadata/places_master.csv")
SCENIC_GPKG = Path("data_raw/tlm/tlm_scenic_transport.gpkg")
BOATS_GPKG  = Path("data_raw/tlm/tlm_boats.gpkg")
OUTPUT_JSON = Path("data_processed/scenic_access_metrics.json")

RADIUS_M = 14_000  # 14 km

_WGS84_TO_LV95 = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)


def read_places(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            {
                "slug": r["slug"].strip(),
                "name": r["name"].strip(),
                "lat":  float(r["lat"]),
                "lon":  float(r["lon"]),
            }
            for r in reader
            if str(r.get("active", "")).strip().lower() == "true"
        ]


def minmax_normalise(values: List[float]) -> List[float]:
    v_min = min(values)
    v_max = max(values)
    v_range = v_max - v_min if v_max > v_min else 1.0
    return [round((v - v_min) / v_range, 4) for v in values]


def main() -> None:
    for p in [PLACES_CSV, SCENIC_GPKG, BOATS_GPKG]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places = read_places(PLACES_CSV)

    print("Loading scenic transport layer...")
    scenic_gdf = gpd.read_file(SCENIC_GPKG).to_crs(2056)
    print("Loading boats layer...")
    boats_gdf  = gpd.read_file(BOATS_GPKG).to_crs(2056)

    # Unique identifier column for deduplication — prefer UUID (stable), then NAME
    def unique_count(gdf: gpd.GeoDataFrame) -> int:
        for col in ("UUID", "uuid", "NAME", "name", "id", "ID"):
            if col in gdf.columns:
                return int(gdf[col].dropna().astype(str).nunique())
        return len(gdf)

    rows: List[Dict[str, Any]] = []

    for place in places:
        e, n = _WGS84_TO_LV95.transform(place["lon"], place["lat"])
        place_buffer = Point(e, n).buffer(RADIUS_M)

        scenic_hits = scenic_gdf[scenic_gdf.intersects(place_buffer)]
        boat_hits   = boats_gdf[boats_gdf.intersects(place_buffer)]

        scenic_count = unique_count(scenic_hits)
        boat_count   = unique_count(boat_hits)

        # Boats weighted 0.5x
        weighted_scenic = scenic_count + boat_count * 0.5

        rows.append({
            "slug":                   place["slug"],
            "name":                   place["name"],
            "scenic_transport_count": scenic_count,
            "boat_count":             boat_count,
            "_weighted_scenic":       weighted_scenic,
        })

    # Min-max normalise
    scenic_norm = minmax_normalise([r["_weighted_scenic"] for r in rows])
    for i, row in enumerate(rows):
        row["scenic_score"] = scenic_norm[i]
        del row["_weighted_scenic"]

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    print(f"  scenic_score range: {min(r['scenic_score'] for r in rows):.3f}–{max(r['scenic_score'] for r in rows):.3f}")


if __name__ == "__main__":
    main()
