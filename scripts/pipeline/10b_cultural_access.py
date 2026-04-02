#!/usr/bin/env python3
"""
10b_cultural_access.py

Score each place on named museums within a 14km radius.

Inputs:
  - metadata/places_master.csv
  - data_raw/osm/osm_switzerland.gpkg  (layer: gis_osm_pois_free)

Output:
  - data_processed/cultural_access_metrics.csv

Columns:
  slug, reachable_named_museums (capped at 20), cultural_access_score (0-1)

Method:
  - Filter OSM POIs to fclass='museum' AND name not null/empty
  - For each base place:
      Count named museums within 14km (Euclidean in EPSG:2056), capped at 20
  - Min-max normalise capped counts across all 185 places
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point

PLACES_CSV = Path("metadata/places_master.csv")
OSM_GPKG   = Path("data_raw/osm/osm_switzerland.gpkg")
POI_LAYER  = "gis_osm_pois_free"
OUTPUT_CSV = Path("data_processed/cultural_access_metrics.csv")

RADIUS_M   = 14_000   # 14 km
MUSEUM_CAP = 20

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
    for p in [PLACES_CSV, OSM_GPKG]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places = read_places(PLACES_CSV)

    print("Loading OSM POIs...")
    pois = gpd.read_file(OSM_GPKG, layer=POI_LAYER).to_crs(2056)
    print(f"  POI columns: {list(pois.columns)}")

    # Filter to museums with a non-empty name
    fclass_lower = pois["fclass"].astype(str).str.lower()
    is_museum = fclass_lower == "museum"

    name_col = None
    for candidate in ("name", "osm_name", "NAME"):
        if candidate in pois.columns:
            name_col = pois[candidate]
            break
    if name_col is None:
        for col in pois.columns:
            if "name" in col.lower():
                name_col = pois[col]
                break

    if name_col is not None:
        has_name = name_col.notna() & (name_col.astype(str).str.strip() != "")
        museums = pois[is_museum & has_name]
    else:
        museums = pois[is_museum]
        print("  WARNING: no name column found — counting all museums without name filter")

    print(f"  Named museums: {len(museums)}")

    rows: List[Dict[str, Any]] = []

    for place in places:
        e, n = _WGS84_TO_LV95.transform(place["lon"], place["lat"])
        place_buffer = Point(e, n).buffer(RADIUS_M)

        count  = int(len(museums[museums.intersects(place_buffer)]))
        capped = min(count, MUSEUM_CAP)

        rows.append({
            "slug":                    place["slug"],
            "name":                    place["name"],
            "reachable_named_museums": capped,
        })

    # Min-max normalise
    norm = minmax_normalise([r["reachable_named_museums"] for r in rows])
    for i, row in enumerate(rows):
        row["cultural_access_score"] = norm[i]

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["slug", "name", "reachable_named_museums", "cultural_access_score"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT_CSV} with {len(rows)} rows")
    scores = [r["cultural_access_score"] for r in rows]
    print(f"  cultural_access_score range: {min(scores):.3f}–{max(scores):.3f}")


if __name__ == "__main__":
    main()
