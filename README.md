# SmartTourismIndex

Swiss tourism ranking pipeline and website data export for discovering **beautiful Swiss base locations** with strong public-transport access and lower tourist pressure than obvious hotspots.

## What this project does

SmartTourismIndex identifies Swiss towns, villages, and small cities that work well as a **tourist base**.

The core idea is not “best destinations in Switzerland.”  
It is:

> Find a beautiful Swiss place to stay that gives you strong access to nature, scenic transport, culture, and water — without the overtourism burden of the most obvious hotspots.

The project is built as an **offline-first data pipeline**:
- ingest raw Swiss public and open datasets
- normalize and merge them per place
- compute place-level metrics and scores
- export lightweight JSON files for the website

This keeps the frontend fast, static-friendly, and easy to deploy.

## Product logic

The ranking model is built around 4 top-level dimensions:
- Base quality — 25%
- Access value — 35%
- Practical comfort — 20%
- Anti-overtourism advantage — 20%

## Current project status

The offline pipeline currently runs end-to-end and produces:
- BFS origin split metrics
- BFS supply / demand / occupancy metrics
- merged BFS place metrics
- climate metrics
- GTFS access metrics
- hiking metrics
- water metrics
- heritage metrics
- OSM museum / restaurant metrics
- final scored place dataset
- website-ready exports

Current known output shape:
- **186** BFS-backed places
- **193** final scored/exported places

## Repository structure

```text
SmartTourismIndex/
├─ README.md
├─ docs/
├─ config/
├─ data_raw/
├─ data_processed/
├─ data_export/
├─ metadata/
├─ scripts/
└─ website/
```

## Core data sources

- BFS tourism CSVs
- MeteoSwiss climate normals
- Swiss GTFS
- swissTLM3D `.gdb`
- OSM GeoPackage
- UNESCO JSON

## Running the pipeline

### Full run
```powershell
powershell -ExecutionPolicy Bypass -File .\run_smart_tourism_pipeline.ps1
```

### Development / skip mode
```powershell
powershell -ExecutionPolicy Bypass -File .\run_smart_tourism_pipeline_skip.ps1
```

## Website integration

The frontend should consume only:
- `data_export/places-index.json`
- `data_export/places/<slug>.json`
- `data_export/version.json`

## What to commit to GitHub

Recommended to commit:
- scripts
- metadata files
- docs
- config
- website code
- README
- `.gitignore`
- `requirements.txt`

Usually **do not commit**:
- `data_raw/`
- `data_processed/`
- large exports if regenerated locally
- `.gdb`
- `.gpkg`
- `.zip`
- `.nc`
