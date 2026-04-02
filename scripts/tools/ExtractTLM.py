#!/usr/bin/env python3
"""
ExtractTLM.py

Extracts individual layers from the swissTLM3D File Geodatabase and saves them
as GeoPackages in data_raw/tlm/. Run this once whenever the GDB is updated.

The GDB is too large to commit to GitHub. The extracted GeoPackages are small
enough to commit and are what the pipeline scripts read.

Input:
  data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb

Outputs in data_raw/tlm/:
  tlm_rivers.gpkg          TLM_FLIESSGEWAESSER      (flowing water)
  tlm_lakes.gpkg           TLM_STEHENDES_GEWAESSER  (standing water / lakes)
  tlm_hiking.gpkg          TLM_WANDERWEG            (marked hiking trails)
  tlm_scenic_transport.gpkg TLM_ERLEBNIS_PANORAMABAHN (scenic/panoramic rail)
  tlm_boats.gpkg           TLM_SCHIFFSFAHRT         (boat/ferry routes)
  tlm_walkability.gpkg     TLM_STRASSE_FUSS         (pedestrian paths)
  tlm_stops.gpkg           TLM_OEV_HALTESTELLE      (public transport stops)

Usage (from project root):
  python scripts/tools/ExtractTLM.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

GDB = Path("data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb")
OUT = Path("data_raw/tlm")

# (gdb_layer_name, output_filename)
EXTRACTIONS = [
    ("TLM_FLIESSGEWAESSER",       "tlm_rivers.gpkg"),
    ("TLM_STEHENDES_GEWAESSER",   "tlm_lakes.gpkg"),
    ("TLM_WANDERWEG",             "tlm_hiking.gpkg"),
    ("TLM_ERLEBNIS_PANORAMABAHN", "tlm_scenic_transport.gpkg"),
    ("TLM_SCHIFFSFAHRT",          "tlm_boats.gpkg"),
    ("TLM_STRASSE_FUSS",          "tlm_walkability.gpkg"),
    ("TLM_OEV_HALTESTELLE",       "tlm_stops.gpkg"),
]


def extract(gdb_layer: str, out_path: Path) -> None:
    if out_path.exists():
        print(f"  SKIP  {out_path.name} (already exists)")
        return
    print(f"  READ  {gdb_layer} ...", end=" ", flush=True)
    gdf = gpd.read_file(GDB, layer=gdb_layer)
    gdf.to_file(out_path, driver="GPKG")
    print(f"→ {out_path.name}  ({len(gdf):,} features)")


def main() -> None:
    if not GDB.exists():
        raise FileNotFoundError(f"Missing GDB: {GDB}")

    OUT.mkdir(parents=True, exist_ok=True)

    for layer_name, filename in EXTRACTIONS:
        extract(layer_name, OUT / filename)

    print("\nDone.")


if __name__ == "__main__":
    main()
