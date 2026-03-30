#!/usr/bin/env python3
"""
10b_cultural_access.py

Score each place on named museums accessible within its reachable commune set.

Inputs:
  - metadata/places_master.csv
  - data_processed/gtfs/gtfs_reachability.json
  - data_raw/osm/osm_switzerland.gpkg  (layer: gis_osm_pois_free)

Output:
  - data_processed/cultural_access_metrics.json

Columns:
  slug, reachable_named_museums, cultural_access_score (0-1 normalised)

Method:
  - Filter OSM POIs to fclass='museum' AND name not null/empty
  - For each base place: union of 3km buffers around reachable commune anchors
  - Count named museums intersecting union, capped at 20
  - Min-max normalise the capped count
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry import Point

PLACES_CSV        = Path("metadata/places_master.csv")
REACHABILITY_JSON = Path("data_processed/gtfs/gtfs_reachability.json")
OSM_GPKG          = Path("data_raw/osm/osm_switzerland.gpkg")
POI_LAYER         = "gis_osm_pois_free"
OUTPUT_JSON       = Path("data_processed/cultural_access_metrics.json")

COMMUNE_BUFFER_M  = 3_000   # 3 km around each reachable commune anchor
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
    reachability: Dict[str, List[str]] = json.loads(REACHABILITY_JSON.read_text(encoding="utf-8"))

    print("Loading OSM POIs...")
    pois = gpd.read_file(OSM_GPKG, layer=POI_LAYER).to_crs(2056)

    # Filter to named museums only
    fclass_lower = pois["fclass"].astype(str).str.lower()
    name_col = pois.get("name", pois.get("osm_name", None))
    if name_col is None:
        # Try to find any name-like column
        for col in pois.columns:
            if "name" in col.lower():
                name_col = pois[col]
                break

    if name_col is not None:
        museums = pois[
            (fclass_lower == "museum") &
            name_col.notna() &
            (name_col.astype(str).str.strip() != "")
        ]
    else:
        museums = pois[fclass_lower == "museum"]
        print("  WARNING: no name column found — using all museums without name filter")

    print(f"  Named museums: {len(museums)}")

    rows: List[Dict[str, Any]] = []
    for place in places:
        slug = place["slug"]
        reachable_slugs = reachability.get(slug, [])

        # Union of 3km buffers around reachable commune anchors + base place
        buffers = []
        for rslt in [slug] + reachable_slugs:
            rp = slug_to_place.get(rslt)
            if rp is None:
                continue
            pt = gpd.GeoSeries([Point(rp["lon"], rp["lat"])], crs=4326).to_crs(2056).iloc[0]
            buffers.append(pt.buffer(COMMUNE_BUFFER_M))

        union_geom = unary_union(buffers) if buffers else \
            gpd.GeoSeries([Point(place["lon"], place["lat"])], crs=4326).to_crs(2056).iloc[0].buffer(COMMUNE_BUFFER_M)

        count = int(len(museums[museums.intersects(union_geom)]))
        capped = min(count, MUSEUM_CAP)

        rows.append({
            "slug":                    slug,
            "name":                    place["name"],
            "reachable_named_museums": capped,
        })

    # Min-max normalise
    norm = minmax_normalise([r["reachable_named_museums"] for r in rows])
    for i, row in enumerate(rows):
        row["cultural_access_score"] = norm[i]

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")
    print(f"  cultural_access_score range: {min(r['cultural_access_score'] for r in rows):.3f}–{max(r['cultural_access_score'] for r in rows):.3f}")


if __name__ == "__main__":
    main()
