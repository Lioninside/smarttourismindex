#!/usr/bin/env python3
"""
10_osm_pois.py

Reads an OSM GeoPackage extract and exports museum/restaurant/historic presence metrics.

Expected input:
  - places_master.csv
  - data_raw/osm/osm_switzerland.gpkg
    OR
  - data_raw/osm/switzerland-latest-free.gpkg

Output:
  - data_processed/osm/osm_poi_metrics.json

MVP logic:
- use gis_osm_pois_free
- count museum POIs within 2 km
- count restaurant POIs within 2 km
- count historic feature POIs within 2 km (castle, monastery, ruins, fort, archaeological)
- create simple local presence labels
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
from shapely.geometry import Point

PLACES_CSV = Path("metadata/places_master.csv")
OSM_GPKG_A = Path("data_raw/osm/osm_switzerland.gpkg")
OSM_GPKG_B = Path("data_raw/osm/switzerland-latest-free.gpkg")
OUTPUT_JSON = Path("data_processed/osm/osm_poi_metrics.json")

POI_LAYER = "gis_osm_pois_free"

HISTORIC_FCLASSES = {"castle", "monastery", "ruins", "fort", "archaeological"}


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


def find_osm_source() -> Path:
    if OSM_GPKG_A.exists():
        return OSM_GPKG_A
    if OSM_GPKG_B.exists():
        return OSM_GPKG_B
    raise FileNotFoundError("Missing OSM GeoPackage")


def read_osm_pois() -> gpd.GeoDataFrame:
    src = find_osm_source()
    gdf = gpd.read_file(src, layer=POI_LAYER)

    if gdf.crs is None:
        raise ValueError("OSM POI layer has no CRS")

    return gdf.to_crs(3857)


def main() -> None:
    places = read_places(PLACES_CSV)
    pois = read_osm_pois()

    # Typical Geofabrik POI schema uses "fclass" for category
    if "fclass" not in pois.columns:
        raise ValueError(f"Expected 'fclass' column in {POI_LAYER}, found: {list(pois.columns)}")

    fclass_lower = pois["fclass"].astype(str).str.lower()
    museums = pois[fclass_lower == "museum"]
    restaurants = pois[fclass_lower == "restaurant"]
    historic = pois[fclass_lower.isin(HISTORIC_FCLASSES)]

    rows: List[Dict[str, Any]] = []
    for place in places:
        point = gpd.GeoSeries([Point(place["lon"], place["lat"])], crs=4326).to_crs(3857).iloc[0]
        buf2 = point.buffer(2000)

        museum_count = int(len(museums[museums.intersects(buf2)]))
        restaurant_count = int(len(restaurants[restaurants.intersects(buf2)]))
        historic_count = int(len(historic[historic.intersects(buf2)]))

        rows.append(
            {
                "slug": place["slug"],
                "name": place["name"],
                "museum_count_2km": museum_count,
                "restaurant_count_2km": restaurant_count,
                "historic_feature_count": historic_count,
                "local_culture_presence": museum_count > 0,
                "local_restaurant_presence": restaurant_count > 0,
            }
        )

    rows.sort(key=lambda x: x["slug"])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUTPUT_JSON} with {len(rows)} rows")


if __name__ == "__main__":
    main()