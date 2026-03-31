#!/usr/bin/env python3
"""
10b_cultural_access.py

Score each place on named museums reachable within 1 hour by PT.

Inputs:
  - metadata/places_master.csv
  - data_processed/gtfs/gtfs_reachability.json
  - data_raw/osm/osm_switzerland.gpkg  (layer: gis_osm_pois_free)

Output:
  - data_processed/cultural_access_metrics.csv

Columns:
  slug, reachable_named_museums (capped at 20), cultural_access_score (0-1)

Method:
  - Filter OSM POIs to fclass='museum' AND name not null/empty
  - For each base place:
      a. Get reachable commune slugs from gtfs_reachability.json
      b. Build union of 3km buffers around all reachable commune anchor points
         (reproject WGS84 -> EPSG:2056 for accurate metre-based buffers)
      c. Count named museums within union, capped at 20
  - Fallback: if place has no reachability entry, use a 40km geographic buffer
  - Min-max normalise capped counts across all 193 places
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Point

PLACES_CSV        = Path("metadata/places_master.csv")
REACHABILITY_JSON = Path("data_processed/gtfs/gtfs_reachability.json")
OSM_GPKG          = Path("data_raw/osm/osm_switzerland.gpkg")
POI_LAYER         = "gis_osm_pois_free"
OUTPUT_CSV        = Path("data_processed/cultural_access_metrics.csv")

COMMUNE_BUFFER_M  = 3_000    # 3 km around each reachable commune anchor
FALLBACK_BUFFER_M = 40_000   # 40 km fallback when no reachability entry
MUSEUM_CAP        = 20


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


def to_lv95_point(lon: float, lat: float) -> Any:
    return gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(2056).iloc[0]


def minmax_normalise(values: List[float]) -> List[float]:
    v_min = min(values)
    v_max = max(values)
    v_range = v_max - v_min if v_max > v_min else 1.0
    return [round((v - v_min) / v_range, 4) for v in values]


def main() -> None:
    for p in [PLACES_CSV, REACHABILITY_JSON, OSM_GPKG]:
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")

    places = read_places(PLACES_CSV)
    slug_to_place = {p["slug"]: p for p in places}
    reachability: Dict[str, List[str]] = json.loads(
        REACHABILITY_JSON.read_text(encoding="utf-8")
    )

    print("Loading OSM POIs...")
    pois = gpd.read_file(OSM_GPKG, layer=POI_LAYER).to_crs(2056)
    print(f"  POI columns: {list(pois.columns)}")

    # Filter to museums with a non-empty name
    fclass_lower = pois["fclass"].astype(str).str.lower()
    is_museum = fclass_lower == "museum"

    # Locate name column (Geofabrik schema uses 'name')
    name_col = None
    for candidate in ("name", "osm_name", "NAME"):
        if candidate in pois.columns:
            name_col = pois[candidate]
            break
    if name_col is None:
        # Fall back to first column containing "name" in its label
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
    fallback_count = 0

    for place in places:
        slug = place["slug"]
        reachable_slugs = reachability.get(slug)

        if reachable_slugs is not None:
            # Build union of 3km buffers around reachable communes + base place
            buffers = []
            for rslt in [slug] + reachable_slugs:
                rp = slug_to_place.get(rslt)
                if rp is None:
                    continue
                buffers.append(to_lv95_point(rp["lon"], rp["lat"]).buffer(COMMUNE_BUFFER_M))
            union_geom = unary_union(buffers) if buffers else \
                to_lv95_point(place["lon"], place["lat"]).buffer(COMMUNE_BUFFER_M)
        else:
            # Fallback: 40km buffer around anchor
            union_geom = to_lv95_point(place["lon"], place["lat"]).buffer(FALLBACK_BUFFER_M)
            fallback_count += 1

        count  = int(len(museums[museums.intersects(union_geom)]))
        capped = min(count, MUSEUM_CAP)

        rows.append({
            "slug":                    slug,
            "name":                    place["name"],
            "reachable_named_museums": capped,
        })

    if fallback_count:
        print(f"  Fallback (40km buffer) used for {fallback_count} places")

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
