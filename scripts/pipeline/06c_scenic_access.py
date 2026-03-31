#!/usr/bin/env python3
"""
06c_scenic_access.py

Score each place on scenic transport and major hiking accessible within its
GTFS-reachable commune set.

Inputs:
  - metadata/places_master.csv
  - data_processed/gtfs/gtfs_reachability.json
  - data_raw/tlm/tlm_scenic_transport.gpkg  (EPSG:2056)
  - data_raw/tlm/tlm_boats.gpkg             (EPSG:2056)
  - data_processed/hiking/hiking_metrics.json

Output:
  - data_processed/scenic_access_metrics.json

Columns:
  slug, scenic_transport_count, boat_count,
  scenic_score (0-1 normalised),
  access_hiking_m, access_hiking_score (0-1 normalised)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Point

PLACES_CSV       = Path("metadata/places_master.csv")
REACHABILITY_JSON = Path("data_processed/gtfs/gtfs_reachability.json")
SCENIC_GPKG      = Path("data_raw/tlm/tlm_scenic_transport.gpkg")
BOATS_GPKG       = Path("data_raw/tlm/tlm_boats.gpkg")
HIKING_JSON      = Path("data_processed/hiking/hiking_metrics.json")
OUTPUT_JSON      = Path("data_processed/scenic_access_metrics.json")

COMMUNE_BUFFER_M = 5_000  # 5 km around each reachable commune anchor
import csv


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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def minmax_normalise(values: List[float]) -> List[float]:
    v_min = min(values)
    v_max = max(values)
    v_range = v_max - v_min if v_max > v_min else 1.0
    return [round((v - v_min) / v_range, 4) for v in values]


def reproject_place(lat: float, lon: float) -> Any:
    return gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(2056).iloc[0]


def main() -> None:
    for p in [PLACES_CSV, REACHABILITY_JSON, SCENIC_GPKG, BOATS_GPKG, HIKING_JSON]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places     = read_places(PLACES_CSV)
    slug_to_place = {p["slug"]: p for p in places}

    reachability: Dict[str, List[str]] = load_json(REACHABILITY_JSON)
    hiking_rows: List[Dict[str, Any]]  = load_json(HIKING_JSON)
    regional_hiking: Dict[str, float]  = {
        r["slug"]: float(r.get("regional_hiking_m", 0))
        for r in hiking_rows
    }

    print("Loading scenic transport layer...")
    scenic_gdf = gpd.read_file(SCENIC_GPKG).to_crs(2056)
    print("Loading boats layer...")
    boats_gdf  = gpd.read_file(BOATS_GPKG).to_crs(2056)

    # Unique identifier column for deduplication — prefer UUID (stable), then NAME
    def unique_ids(gdf: gpd.GeoDataFrame) -> set:
        for col in ("UUID", "uuid", "NAME", "name", "id", "ID"):
            if col in gdf.columns:
                return set(gdf[col].dropna().astype(str).unique())
        return set(range(len(gdf)))

    rows: List[Dict[str, Any]] = []

    for place in places:
        slug = place["slug"]
        reachable_slugs = reachability.get(slug, [])

        # Build union geometry of 5km buffers around reachable commune anchors
        buffers = []
        for rslt in reachable_slugs:
            rp = slug_to_place.get(rslt)
            if rp is None:
                continue
            pt = reproject_place(rp["lat"], rp["lon"])
            buffers.append(pt.buffer(COMMUNE_BUFFER_M))
        # Also include the base place itself
        base_pt = reproject_place(place["lat"], place["lon"])
        buffers.append(base_pt.buffer(COMMUNE_BUFFER_M))

        if not buffers:
            union_geom = base_pt.buffer(COMMUNE_BUFFER_M)
        else:
            union_geom = unary_union(buffers)

        # Count unique scenic transport lines intersecting the union
        scenic_hits = scenic_gdf[scenic_gdf.intersects(union_geom)]
        boat_hits   = boats_gdf[boats_gdf.intersects(union_geom)]

        scenic_count = len(unique_ids(scenic_hits))
        boat_count   = len(unique_ids(boat_hits))

        # Weighted score: boats count 0.5x
        weighted_scenic = scenic_count + boat_count * 0.5

        # Access hiking: sum regional_hiking_m for all reachable communes
        access_hiking_m = sum(
            regional_hiking.get(rslt, 0.0) for rslt in reachable_slugs
        )

        rows.append({
            "slug":                  slug,
            "name":                  place["name"],
            "scenic_transport_count": scenic_count,
            "boat_count":            boat_count,
            "_weighted_scenic":      weighted_scenic,   # temp for normalisation
            "access_hiking_m":       round(access_hiking_m, 1),
        })

    # Min-max normalise scenic and access hiking
    scenic_norm  = minmax_normalise([r["_weighted_scenic"] for r in rows])
    hiking_norm  = minmax_normalise([r["access_hiking_m"]  for r in rows])

    for i, row in enumerate(rows):
        row["scenic_score"]        = scenic_norm[i]
        row["access_hiking_score"] = hiking_norm[i]
        del row["_weighted_scenic"]

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    print(f"  scenic_score range: {min(r['scenic_score'] for r in rows):.3f}–{max(r['scenic_score'] for r in rows):.3f}")


if __name__ == "__main__":
    main()
