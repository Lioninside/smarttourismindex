# SmartTourismIndex — Engineering Handover

## Executive summary

SmartTourismIndex is an offline-first Swiss tourism ranking pipeline plus website data-export layer.

Its purpose is to identify **beautiful Swiss base locations** for tourists that are:
- less overrun than obvious hotspots
- strong for 1-hour public transport access
- beautiful / walkable / pleasant to stay in
- good for nature, hiking, water, scenic transport, and culture
- usable without a car
- updated from real source data rather than editorial-only content

The architecture intentionally separates:
1. raw source data
2. offline processing / scoring
3. lightweight website-ready export files

## Locked ranking model

### Base quality — 25%
- heritage / old-town quality
- walkable center
- local culture presence
- local restaurant presence
- local water setting

### Access value — 35%
- scenic transport access
- nature access
- water access
- cultural access
- diversity bonus

### Practical comfort — 20%
- PT strength
- climate comfort
- accommodation readiness

### Anti-overtourism advantage — 20%
- hiddenness advantage
- tourism pressure proxy
- overtourism penalty

## Current pipeline scripts

- `01_setup_project.ps1`
- `02_bfs_origin_split.py`
- `03_bfs_supply_demand.py`
- `04_bfs_merge.py`
- `05_climate.py`
- `06_gtfs_access.py`
- `07_hiking.py`
- `08_water.py`
- `09_heritage.py`
- `10_osm_pois.py`
- `11_merge_score.py`
- `12_export_site_data.py`

## Current successful state

At the latest successful run:
- BFS origin split: 186 rows
- BFS supply / demand: 186 rows
- BFS merged: 186 rows
- climate metrics: 193 rows
- GTFS metrics: 193 rows
- hiking metrics: 193 rows
- water metrics: 193 rows
- heritage metrics: 193 rows
- OSM POI metrics: 193 rows
- final place scores: 193 rows
- exported place detail files: 193

## Important engineering issues already solved

### BFS placeholders
BFS CSVs can contain `...` and `-`. Parsers were updated to treat them as zero.

### MeteoSwiss NetCDF handling
The climate files require:
- `decode_times=False`
- manual month normalization
- WGS84 to LV95 coordinate transformation
- selection by `N` / `E`, not direct `lat` / `lon`

### BFS alias mismatches
Several commune names needed aliases in `place_mapping.json`.

### Duplicate slug issue
`Moutier (BE)` and `Moutier (JU)` initially shared a slug.  
This was fixed by giving `Moutier (JU)` the slug `moutier-ju`.

### OSM layer mismatch
The OSM GeoPackage does not expose a `points` layer.
The correct layer is:
- `gis_osm_pois_free`

### swissTLM3D usage
The project now uses the full `swissTLM3D_2026_LV95_LN02.gdb` directly instead of separate thematic downloads.

## Important swissTLM3D layers

Already used:
- `TLM_FLIESSGEWAESSER`
- `TLM_STEHENDES_GEWAESSER`
- `TLM_STRASSE`

Strong future candidates:
- `TLM_UEBRIGE_BAHN`
- `TLM_EISENBAHN`
- `TLM_SCHIFFFAHRT`
- `TLM_HALTESTELLE`
- `TLM_SIEDLUNGSNAME_ZENTRUM`

## Key future improvements

1. Refine `11_merge_score.py`
2. Add scenic transport enrichment using swissTLM3D
3. Improve ISOS / heritage logic
4. Improve center-point / walkability logic
5. Introduce better rebuild / dependency tooling

## Operational guidance

- Keep large source files in `data_raw/`
- Do not commit large raw / processed data to GitHub
- Regenerate outputs from pipeline scripts instead of editing exported JSON manually
- Use the skip runner during development
