# Update Workflow

This document describes how to refresh data and rerun the SmartTourismIndex pipeline safely.

## General rule
Do not manually edit processed outputs or website export JSON files.

Always:
1. update raw data
2. rerun the relevant pipeline steps
3. regenerate final score and export files

## Full run
```powershell
powershell -ExecutionPolicy Bypass -File .\run_smart_tourism_pipeline.ps1
```

## Development / skip run
```powershell
powershell -ExecutionPolicy Bypass -File .\run_smart_tourism_pipeline_skip.ps1
```

## Refreshing BFS only
Replace files in `data_raw/bfs/`, then rerun:
- `02_bfs_origin_split.py`
- `03_bfs_supply_demand.py`
- `04_bfs_merge.py`
- `11_merge_score.py`
- `12_export_site_data.py`

## Refreshing climate only
Replace files in `data_raw/climate/`, then rerun:
- `05_climate.py`
- `11_merge_score.py`
- `12_export_site_data.py`

## Refreshing GTFS only
Replace files in `data_raw/gtfs/`, then rerun:
- `06_gtfs_access.py`
- `11_merge_score.py`
- `12_export_site_data.py`

## Refreshing swissTLM3D only
If water logic changed:
- rerun `08_water.py`

If hiking logic changed:
- rerun `07_hiking.py`

Then rerun:
- `11_merge_score.py`
- `12_export_site_data.py`

## Refreshing OSM only
Replace files in `data_raw/osm/`, then rerun:
- `10_osm_pois.py`
- `11_merge_score.py`
- `12_export_site_data.py`

## Changing place metadata
If you change:
- `places_master.csv`
- `place_mapping.json`

assume broad downstream impact.

Safe approach:
- clear `data_processed/`
- clear `data_export/`
- rerun full pipeline

## Sanity checks after updates
Verify:
- no parser crashes
- BFS row counts look plausible
- final scored row count is reasonable
- exported detail files exist
- ranking still looks plausible
