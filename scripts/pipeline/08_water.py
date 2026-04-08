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

Water signal used for scoring (water_equiv_2km_m2):
  - Lakes: clipped polygon area in m²  (Lake Thun next to Spiez >> small pond)
  - Rivers: clipped length × per-segment width from TLM BREITENKLASSE attribute
    (wide rivers like Aare/Rhine score high; long but narrow mountain streams
     score low because their width class is 1–2, giving them 0.5–3 m width)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.ops import polygonize, unary_union

PLACES_CSV   = Path("metadata/places_master.csv")
RIVERS_GPKG  = Path("data_raw/tlm/tlm_rivers.gpkg")
LAKES_GPKG   = Path("data_raw/tlm/tlm_lakes.gpkg")
OUTPUT_JSON  = Path("data_processed/water/water_metrics.json")

BUFFER_LOCAL_M  = 2000   # water within 2km → local_water = True
BUFFER_NEARBY_M = 10000  # water within 10km → reachable_water = True

# TLM BREITENKLASSE → representative width in metres.
# Used to convert river segment length to an equivalent water area so that
# wide rivers (Aare, Rhine) contribute proportionally more than narrow streams.
# Segments without a valid BREITENKLASSE get RIVER_WIDTH_FALLBACK_M.
BREITENKLASSE_WIDTH: Dict[int, float] = {
    1: 0.5,   # < 1 m   — tiny ditch / brook
    2: 3.0,   # 1–5 m   — small stream
    3: 10.0,  # 5–15 m  — medium stream
    4: 30.0,  # 15–50 m — river
    5: 75.0,  # > 50 m  — major river (Aare, Rhine, Rhone …)
}
RIVER_WIDTH_FALLBACK_M = 3.0  # conservative default for unknown segments

# Cap lake area contribution per buffer at 1 km² (1,000,000 m²).
# Without this, places whose 2km circle mostly overlaps a large lake
# (e.g. Ingenbohl on Vierwaldstättersee) score 5–6 million m² while
# river cities score ~50,000 m² — a 100× gap that dominates the ranking.
# The cap still strongly rewards lakeside places over inland ones while
# keeping the scale comparable to the river metric.
LAKE_AREA_CAP_M2 = 1_000_000  # 1 km²

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


def _polygonize_lakes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Convert lake boundary lines to filled polygon areas.

    swissTLM3D TLM_STEHENDES_GEWAESSER stores lake outlines as closed
    LineStrings rather than filled Polygons.  Polygonizing reconstructs
    the filled areas so that .area returns the correct lake surface in m².

    If the geometries are already Polygons (future-proof), this is a no-op.
    If polygonize yields no results (malformed data), the original GDF is
    returned and lake area will be 0 (safe degradation back to river-only).
    """
    if gdf.empty:
        return gdf

    geom_types = set(gdf.geom_type.dropna().unique())

    # Already polygons — nothing to do
    if geom_types <= {"Polygon", "MultiPolygon"}:
        return gdf

    # LinearRing geometries: wrap each directly in a Polygon
    if geom_types <= {"LinearRing"}:
        polys = [Polygon(g) for g in gdf.geometry if g is not None]
        if polys:
            return gpd.GeoDataFrame(geometry=polys, crs=gdf.crs)
        return gdf

    # LineString / MultiLineString: merge and polygonize
    if geom_types <= {"LineString", "MultiLineString", "LinearRing"}:
        merged = unary_union(gdf.geometry)
        polys  = list(polygonize(merged))
        if polys:
            print(f"  [lakes] polygonized {len(gdf):,} boundary lines "
                  f"→ {len(polys):,} lake polygons")
            return gpd.GeoDataFrame(geometry=polys, crs=gdf.crs)
        print("  [lakes] WARNING: polygonize returned no polygons — "
              "lake area contribution will be 0")
        return gdf

    # Mixed or unexpected geometry types — skip conversion
    print(f"  [lakes] WARNING: unexpected geometry types {geom_types}, "
          "skipping polygonize")
    return gdf


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

    # TLM lakes are stored as closed boundary lines, not filled polygons.
    # Polygonize converts them so .area returns the actual lake surface area.
    standing = _polygonize_lakes(standing)

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


def _river_equiv_area(rivers: gpd.GeoDataFrame, buf) -> float:
    """Equivalent area (m²) for river segments clipped to buffer.

    Each segment's clipped length is multiplied by its width derived from
    BREITENKLASSE so that wide rivers (Aare, Rhine) dominate over long but
    narrow mountain streams. Segments without a valid BREITENKLASSE get a
    conservative fallback width.
    """
    if rivers.empty:
        return 0.0

    clipped_lengths = rivers.geometry.intersection(buf).length

    if "BREITENKLASSE" in rivers.columns:
        widths = (
            rivers["BREITENKLASSE"]
            .map(BREITENKLASSE_WIDTH)
            .fillna(RIVER_WIDTH_FALLBACK_M)
        )
    else:
        widths = pd.Series(RIVER_WIDTH_FALLBACK_M, index=rivers.index)

    return float((clipped_lengths * widths).sum())


def _water_equivalent_m2(features: gpd.GeoDataFrame, buf) -> float:
    """Combined water area equivalent within buffer (m²).

    Lakes: clipped polygon area.
    Rivers/streams: clipped length × per-segment width from BREITENKLASSE.
    """
    if features.empty:
        return 0.0

    lakes  = features[features["water_type"] == "standing"]
    rivers = features[features["water_type"] == "flowing"]

    lake_area  = float(lakes.geometry.intersection(buf).area.sum()) if not lakes.empty else 0.0
    lake_area  = min(lake_area, LAKE_AREA_CAP_M2)
    river_area = _river_equiv_area(rivers, buf)

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
    print(f"  River widths by BREITENKLASSE: {BREITENKLASSE_WIDTH}")
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
