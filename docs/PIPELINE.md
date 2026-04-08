# SmartTourismIndex — Pipeline Reference

> Engineering reference for the data pipeline. Stable across versions — update only when scripts, data sources, or architecture change.

---

## Architecture overview

```
data_raw/          ← source files, local only (.gitignored)
    bfs/           ← BFS CSV exports
    swisstopo/     ← swissTLM3D GDB
    osm/           ← OSM GeoPackage (Switzerland)
    climate/       ← MeteoSwiss NetCDF normals
    gtfs/          ← SBB GTFS ZIP
    heritage/      ← ISOS GeoJSON + Swiss UNESCO sites
    swiss_unesco_sites.json

data_processed/    ← pipeline outputs, committed to git
    bfs/
    climate/
    gtfs/
    hiking/
    water/
    heritage/
    osm/
    final/
    sbbapi/        ← SBB API reachability cache (local only, .gitignored)

data_export/       ← website-ready JSON, committed to git
    places-index.json
    version.json
    places/<slug>.json
```

`data_raw/` and `data_processed/sbbapi/` are gitignored. Everything else in `data_processed/` and `data_export/` is committed.

---

## Pipeline execution order

```
02_bfs_origin_split.py
03_bfs_supply_demand.py
04_bfs_merge.py
05_climate.py
05b_tourism_intensity_seasonality.py
06_gtfs_access.py
06b_gtfs_reachability.py         ← reads sbbapi cache, not in main runner
06c_scenic_access.py
06d_destination_pull.py
07_hiking.py
07b_walkability.py
08_water.py
09_heritage.py
10_osm_pois.py
10b_cultural_access.py
11_merge_score.py
12_export_site_data.py
```

Run from **repo root** via PowerShell:

```powershell
# Full run
powershell -ExecutionPolicy Bypass -File .\scripts\run_smart_tourism_pipeline.ps1

# Skip already-complete steps (development)
powershell -ExecutionPolicy Bypass -File .\scripts\run_smart_tourism_pipeline_skip.ps1
```

---

## Script reference

### `02_bfs_origin_split.py`
Parses BFS origin split CSV. Outputs: `data_processed/bfs/bfs_origin_split_2025.json` (186 rows).

### `03_bfs_supply_demand.py`
Parses BFS supply/demand/occupancy CSV. Outputs: `data_processed/bfs/bfs_supply_demand_2025.json` (186 rows).

### `04_bfs_merge.py`
Merges BFS outputs. Outputs: `data_processed/bfs/bfs_place_metrics_2025.json` (186 rows).

### `05_climate.py`
Reads MeteoSwiss NetCDF normals. Outputs: `data_processed/climate/climate_metrics_jja.json` (185 rows).

Key implementation details:
- `decode_times=False` — MeteoSwiss files use non-standard time encoding (`months since 1991-01-01`)
- WGS84 → LV95 coordinate transformation before grid lookup
- Dimensions are `N` / `E`, not `lat` / `lon` (those are helper coordinates only)

### `05b_tourism_intensity_seasonality.py`
Computes `tourism_intensity = overnights / residents` and 12-month indexed seasonality. Outputs: `data_processed/tourism_intensity_seasonality.csv` (186 rows). Note: Laténa has no STATPOP population entry — uses median fallback.

### `06_gtfs_access.py`
GTFS-based PT access metrics (nearest stop, frequency). Outputs: `data_processed/gtfs/gtfs_access_metrics.json` (185 rows).

### `06b_gtfs_reachability.py`
Reads SBB API reachability cache from `data_processed/sbbapi/sbbAPI_reachability.json`. Builds per-place reachable commune list (1h PT travel). **Not in the main runner** — sbbapi data is static and regenerated annually only. Outputs feed into `06d` and `10b`.

### `06c_scenic_access.py`
Counts scenic transport lines and boats within 14km. Reads `tlm_scenic_transport.gpkg` and `tlm_boats.gpkg`. Outputs: `data_processed/scenic_access_metrics.json`.

### `06d_destination_pull.py`
Sums BFS overnights of reachable communes, log-normalised. Outputs: `data_processed/destination_pull_metrics.json`.

### `07_hiking.py`
Local hiking (4km) and regional hiking (20km) from TLM WANDERWEGE. Outputs: `data_processed/hiking/hiking_metrics.json`.

### `07b_walkability.py`
Pedestrian and living-street road metres within 3km from OSM. Source layer: `gis_osm_roads_free`, filter: `fclass IN ('pedestrian', 'living_street')`. Outputs: `data_processed/walkability_metrics.json`.

### `08_water.py`
Lakes + rivers within 2km, area-equivalent metric. Outputs: `data_processed/water/water_metrics.json`.

Two steps before scoring:
1. `_polygonize_lakes()` — converts TLM lake boundary LineStrings to filled Polygons using `shapely.ops.polygonize`
2. `min(lake_area, 1_000_000)` — caps lake contribution at 1 km² per buffer

### `09_heritage.py`
ISOS national inventory match within 4km buffer (EPSG:2056). Source: `data_raw/heritage/isos_national.geojson`. Outputs: `data_processed/heritage/heritage_metrics.json` (150 matches of 185 places).

### `10_osm_pois.py`
OSM POI counts (museums, restaurants). Outputs: `data_processed/osm/osm_poi_metrics.json`.

### `10b_cultural_access.py`
Named OSM museums in reachable communes. Outputs: `data_processed/cultural_access_metrics.csv`.

### `11_merge_score.py`
Merges all processed layers, computes Base + Access + Total score. Applies exclude list (`scripts/pipeline/exclude.json`). Outputs: `data_processed/final/place_scores.json` (184 rows after excluding Monteceneri).

### `12_export_site_data.py`
Exports website-ready JSON. Outputs: `data_export/places-index.json`, `data_export/version.json`, `data_export/places/<slug>.json` (184 files).

---

## One-time setup steps

Before running the pipeline for the first time on a new machine:

### 1. Extract TLM layers
```powershell
py scripts/tools/ExtractTLM.py
```
Extracts required layers from `swissTLM3D_2026_LV95_LN02.gdb` into GeoPackages under `data_raw/tlm/`. Takes ~2–3 minutes for TLM_STRASSE. Use `--force` to re-extract.

### 2. Download ISOS data
```powershell
py scripts/tools/GetHeritage.py
```
Queries geo.admin.ch MapServer grid (30km × 30km tiles, required because Switzerland-wide bbox returns empty). Saves `data_raw/heritage/isos_national.geojson` (1,255 national ISOS settlements).

### 3. Python packages
```powershell
python -m pip install xarray netCDF4 pandas geopandas shapely pyogrio fiona pyproj
```

---

## Key data files

| File | Description |
|---|---|
| `metadata/places_master.csv` | Canonical place list (slug, name, canton, lat/lon, station name) |
| `metadata/place_mapping.json` | BFS commune name → slug alias map |
| `scripts/pipeline/exclude.json` | Places excluded from final output (currently: `["monteceneri"]`) |
| `data_processed/sbbapi/sbbAPI_reachability.json` | SBB API reachable commune cache — regenerate after Dec timetable |

---

## Known engineering issues

### TLM OBJEKTART codes are integers
`TLM_STRASSE.OBJEKTART` stores integer codes, not strings. Key values: 5 = Fussweg, 7 = Trottoir, 9 = Weg.

### TLM AUSSER_BETRIEB encoding is inverted
In `TLM_UEBRIGE_BAHN.AUSSER_BETRIEB`: `1` = active (keep), `2` = out of service (exclude). Filter: `AUSSER_BETRIEB == 1`.

### ISOS CRS must be set, not reprojected
ISOS geometries are stored in LV95 but may lack a CRS tag. Use `gdf.set_crs(2056)` before any spatial operations — `to_crs(2056)` on an untagged geometry produces wrong coordinates.

### BFS placeholders
BFS CSV files use `...` and `-` for suppressed values. Parsers treat them as zero.

### Spatial operations require EPSG:2056
All buffer and distance calculations must reproject place coordinates from WGS84 to EPSG:2056 before applying metre-based buffers. Degree-based distance is not valid for Swiss spatial analysis.

### SBB API reachability cache is static
`data_processed/sbbapi/` contains a pre-computed reachability matrix. It is not regenerated by the main pipeline runner. Regenerate annually after the December SBB timetable update by running `06b_gtfs_reachability.py` separately. Keep this folder local-only (gitignored).

### Tourism intensity outliers
Zermatt, Lauterbrunnen, and Samnaun have extreme `tourism_intensity` values (210–270). Apply 99th percentile clip in `11_merge_score.py` before normalisation.

---

## Sanity checks after full pipeline run

- 184 places in `data_export/places-index.json` (185 scored, 1 excluded)
- `monteceneri` absent from output
- `data_processed/water/water_metrics.json` entries have `water_equiv_2km_m2` field
- Spiez, Beckenried, Vitznau: `water_equiv_2km_m2` > 1,000,000 m² (capped) — `equiv_ha ≈ 100`
- Bern, Basel: meaningful water score from Aare / Rhine
- Zermatt, Lauterbrunnen, Samnaun: rank near bottom (high OT penalty)
- Schaffhausen: heritage = 100.0, isos_name = "Schaffhausen (Stadt)"
- Locarno: Tourism Pressure = LOW (intensity ~9.5, despite 314K overnights)

---

## Operational rules

- Never manually edit files in `data_export/` — always regenerate via `12_export_site_data.py`
- `places_master.csv` coordinate changes require full pipeline rerun (at minimum steps 05–12)
- `place_mapping.json` alias changes require full pipeline rerun
- `exclude.json` changes require rerun of steps 11–12 only
- Run `run_smart_tourism_pipeline_skip.ps1` during development to skip already-complete steps
