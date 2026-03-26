# SmartTourismIndex

Offline-first Swiss tourism ranking pipeline and website export for identifying **beautiful Swiss base locations** with strong public transport access and lower overtourism pressure than the obvious hotspots.

## Purpose

SmartTourismIndex is designed to answer this question:

> Where should a tourist stay in Switzerland if they want a beautiful, practical base with strong access to nature, scenic transport, water, and culture — without defaulting to the most crowded places?

This is **not** a generic “top destinations in Switzerland” project.  
It is specifically a **base-location discovery and ranking system**.

The site aims to highlight places that are:
- attractive in their own right
- usable without a car
- strong for day trips and local access
- less burdened by overtourism than the most famous Swiss destinations

---

## Product model

The current ranking model is built around 4 weighted dimensions:

### 1. Base quality — 25%
How strong is the place itself as a base?

Examples:
- heritage / old-town quality
- walkable center
- local cultural presence
- local restaurant presence
- local water setting

### 2. Access value — 35%
What can a tourist unlock from this base within roughly 1 hour by public transport?

Examples:
- scenic transport access
- hiking / nature
- water access
- cultural access
- diversity of reachable experiences

### 3. Practical comfort — 20%
How easy and pleasant is it to stay there without a car?

Examples:
- PT strength
- summer climate comfort
- accommodation readiness

### 4. Anti-overtourism advantage — 20%
How much does the place avoid the downsides of obvious hotspots while still being strong?

Examples:
- tourism pressure proxy
- hiddenness advantage
- overtourism penalty

---

## Current state

The pipeline currently runs end-to-end and produces:

- BFS origin split metrics
- BFS supply / demand / occupancy metrics
- merged BFS place metrics
- climate metrics
- GTFS access metrics
- hiking metrics
- water metrics
- heritage metrics
- OSM museum / restaurant metrics
- final place scores
- website-ready JSON export

Current known output shape:
- **186** BFS-backed places
- **193** final scored/exported places

This difference is expected because the project includes curated additions beyond the strict BFS-backed place universe.

---

## Repository structure

```text
SmartTourismIndex/
├─ README.md
├─ .gitignore
├─ requirements.txt
│
├─ docs/
│  ├─ ENGINEERING_HANDOVER.md
│  ├─ DATA_SOURCES.md
│  ├─ SCORING_MODEL.md
│  └─ UPDATE_WORKFLOW.md
│
├─ config/
│
├─ metadata/
│  ├─ place_mapping.json
│  ├─ places_master.csv
│  └─ places_master_template.csv
│
├─ scripts/
│  ├─ setup/
│  │  └─ 01_setup_project.ps1
│  │
│  ├─ pipeline/
│  │  ├─ 02_bfs_origin_split.py
│  │  ├─ 03_bfs_supply_demand.py
│  │  ├─ 04_bfs_merge.py
│  │  ├─ 05_climate.py
│  │  ├─ 06_gtfs_access.py
│  │  ├─ 07_hiking.py
│  │  ├─ 08_water.py
│  │  ├─ 09_heritage.py
│  │  ├─ 10_osm_pois.py
│  │  ├─ 11_merge_score.py
│  │  └─ 12_export_site_data.py
│  │
│  ├─ tools/
│  │  ├─ check_bfs_duplicates.py
│  │  ├─ check_bfs_merge_diff.py
│  │  ├─ fix_bfs_aliases.py
│  │  ├─ inspect_climate.py
│  │  ├─ inspect_gdb_layers.py
│  │  └─ inspect_osm_layers.py
│  │
│  ├─ run_smart_tourism_pipeline.ps1
│  └─ run_smart_tourism_pipeline_skip.ps1
│
├─ data_raw/
├─ data_processed/
├─ data_export/
└─ website/
```

---

## Core data sources

### BFS tourism CSVs
Used for:
- arrivals
- overnight stays
- accommodation supply
- occupancy
- domestic vs international split
- tourism pressure logic

### MeteoSwiss climate normals
Used for:
- summer temperature
- summer precipitation
- summer sunshine

### Swiss GTFS
Used for:
- nearest anchor stop
- PT strength proxy
- route richness

### swissTLM3D
Used for:
- water
- hiking

Strong future potential for:
- scenic transport
- settlement centers
- improved walkability / base-quality logic

Current working file:
- `data_raw/swisstopo/swissTLM3D_2026_LV95_LN02.gdb`

### OSM GeoPackage
Used for:
- museums
- restaurants

Current working layer:
- `gis_osm_pois_free`

### UNESCO
Used for:
- UNESCO enrichment
- heritage / culture boost

---

## Important swissTLM3D layers

### Already used
- `TLM_FLIESSGEWAESSER`
- `TLM_STEHENDES_GEWAESSER`
- `TLM_STRASSE`

### High-value future candidates
- `TLM_UEBRIGE_BAHN`
- `TLM_EISENBAHN`
- `TLM_SCHIFFFAHRT`
- `TLM_HALTESTELLE`
- `TLM_SIEDLUNGSNAME_ZENTRUM`

Potential future uses:
- scenic transport classification
- cable cars / gondolas / funiculars
- boat trip access
- better settlement center points
- better walkability and base-quality proxies

---

## Metadata files

### `metadata/places_master.csv`
Canonical place list used by the pipeline.

Key fields:
- `slug`
- `name`
- `canton`
- `tourism_region`
- `lat`
- `lon`
- `center_lat`
- `center_lon`
- `main_station_name`
- `place_type`
- `active`

### `metadata/place_mapping.json`
Maps source-specific place names to canonical SmartTourismIndex places.

This is especially important for:
- BFS alias handling
- name mismatches
- canton-suffixed place names
- curated normalization

---

## Pipeline scripts

### Setup
#### `scripts/setup/01_setup_project.ps1`
Creates expected local folders and supports initial setup.

### Core pipeline
#### `scripts/pipeline/02_bfs_origin_split.py`
Parses BFS origin split and exports:
- `data_processed/bfs/bfs_origin_split_2025.json`

#### `scripts/pipeline/03_bfs_supply_demand.py`
Parses BFS supply / demand / occupancy and exports:
- `data_processed/bfs/bfs_supply_demand_2025.json`

#### `scripts/pipeline/04_bfs_merge.py`
Merges BFS outputs into:
- `data_processed/bfs/bfs_place_metrics_2025.json`

#### `scripts/pipeline/05_climate.py`
Reads MeteoSwiss NetCDF normals and exports:
- `data_processed/climate/climate_metrics_jja.json`

Important implementation details:
- uses `decode_times=False`
- manually normalizes months
- transforms WGS84 to LV95
- selects by `N` / `E`

#### `scripts/pipeline/06_gtfs_access.py`
Creates GTFS-based PT access metrics:
- `data_processed/gtfs/gtfs_access_metrics.json`

#### `scripts/pipeline/07_hiking.py`
Reads hiking access from swissTLM3D:
- `data_processed/hiking/hiking_metrics.json`

#### `scripts/pipeline/08_water.py`
Reads water access from swissTLM3D:
- `data_processed/water/water_metrics.json`

#### `scripts/pipeline/09_heritage.py`
Creates basic heritage / UNESCO layer:
- `data_processed/heritage/heritage_metrics.json`

#### `scripts/pipeline/10_osm_pois.py`
Reads museum / restaurant POIs from OSM:
- `data_processed/osm/osm_poi_metrics.json`

#### `scripts/pipeline/11_merge_score.py`
Merges all processed layers and creates:
- `data_processed/final/place_scores.json`

Important note:
- current scoring logic is **MVP-grade**
- this is a major future refinement area

#### `scripts/pipeline/12_export_site_data.py`
Exports frontend-ready JSON files:
- `data_export/places-index.json`
- `data_export/version.json`
- `data_export/places/<slug>.json`

---

## Utility / debug scripts

These are useful during development and troubleshooting:

- `scripts/tools/check_bfs_duplicates.py`
- `scripts/tools/check_bfs_merge_diff.py`
- `scripts/tools/fix_bfs_aliases.py`
- `scripts/tools/inspect_climate.py`
- `scripts/tools/inspect_gdb_layers.py`
- `scripts/tools/inspect_osm_layers.py`

---

## Running the pipeline

Run from the **repo root**.

### Full run
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_smart_tourism_pipeline.ps1
```

### Development / skip mode
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_smart_tourism_pipeline_skip.ps1
```

The skip runner is recommended during development because it avoids rerunning steps whose outputs already exist.

---

## Local setup

### Python packages
Recommended install:

```powershell
python -m pip install xarray netCDF4 pandas geopandas shapely pyogrio fiona pyproj
```

### Working directory
The runners set the working directory to the repo root, so the Python scripts can continue to use relative paths like:
- `data_raw/...`
- `metadata/...`
- `data_processed/...`

### Raw data location
Large source files should stay under:
- `data_raw/`

Large generated files should stay under:
- `data_processed/`
- `data_export/`

---

## Important issues already solved

### BFS placeholders
BFS files can contain values like:
- `...`
- `-`

The parsers were updated so these are treated as zero.

### MeteoSwiss time decoding
The climate NetCDF files use:
- `months since 1991-01-01`

This required:
- `decode_times=False`
- manual month normalization

### MeteoSwiss coordinate handling
The files use:
- `N` / `E` as real selectable dimensions
- `lat` / `lon` as helper coordinates only

This required:
- WGS84 → LV95 transformation
- selection by `N` / `E`

### BFS alias mismatches
Several commune names required alias handling in `metadata/place_mapping.json`.

Examples:
- `Brienz (BE)`
- `Buchs (SG)`
- `Eschenbach (SG)`
- `Küssnacht (SZ)`
- `Teufen (AR)`
- `Wil (SG)`
- `Moutier (JU)`

### Duplicate slug issue
`Moutier (BE)` and `Moutier (JU)` originally pointed to the same slug.

This was fixed by assigning:
- `Moutier (JU)` → `moutier-ju`

### OSM layer mismatch
The OSM GeoPackage does not expose a `points` layer.
The correct POI layer is:
- `gis_osm_pois_free`

### swissTLM3D usage
Instead of relying on separate thematic downloads, the project now uses the full:
- `swissTLM3D_2026_LV95_LN02.gdb`

This is cleaner and more extensible.

---

## Current outputs

At the last successful known state:
- BFS origin split: **186 rows**
- BFS supply / demand: **186 rows**
- BFS merged: **186 rows**
- climate metrics: **193 rows**
- GTFS metrics: **193 rows**
- hiking metrics: **193 rows**
- water metrics: **193 rows**
- heritage metrics: **193 rows**
- OSM POI metrics: **193 rows**
- final place scores: **193 rows**
- exported place detail files: **193**

### Why 186 vs 193?
- **186** = BFS-backed places
- **193** = full export universe including curated additions

This is expected and intentional.

---

## Website integration

The frontend should consume only:
- `data_export/places-index.json`
- `data_export/places/<slug>.json`
- `data_export/version.json`

The website should **not** read:
- raw geodata
- NetCDF
- GTFS ZIP
- `.gdb`
- large GeoPackages

The entire architecture is built around this separation.

---

## GitHub guidance

### Recommended to commit
- `README.md`
- `docs/`
- `config/`
- `metadata/`
- `scripts/`
- `website/`
- `.gitignore`
- `requirements.txt`

### Usually do not commit
- `data_raw/`
- `data_processed/`
- `data_export/`
- `.gdb`
- `.gpkg`
- `.zip`
- `.nc`

---

## Recommended future improvements

### 1. Improve scoring quality
`11_merge_score.py` is the biggest current quality bottleneck.

Main future work:
- better normalization
- stronger weighting logic
- better hiddenness logic
- clearer missing-data handling
- deeper scenic transport logic

### 2. Expand swissTLM3D usage
Use additional layers for:
- scenic transport
- better center points
- better walkability
- better base-quality proxies

### 3. Improve heritage / old-town logic
Current heritage logic is still shallow and should be improved, especially through stronger ISOS integration.

### 4. Improve rebuild tooling
The skip runner works well, but future improvements could include:
- dependency-aware rebuilds
- more explicit invalidation logic
- better local path configuration

---

## Immediate next priorities

1. integrate real exported ranking into the website
2. refine `scripts/pipeline/11_merge_score.py`
3. add scenic transport enrichment using swissTLM3D
4. improve heritage / old-town scoring
5. improve center-point / walkability logic
6. keep repo structure and docs aligned with the real codebase

---

## Summary

SmartTourismIndex is now past the “make it run” stage.

It already has:
- real Swiss datasets connected
- a working offline processing pipeline
- real exported website data
- documented engineering structure
- development tooling for iterative reruns

The next phase is about:
- improving quality
- improving scoring
- enriching the model
- integrating the real outputs into the frontend
