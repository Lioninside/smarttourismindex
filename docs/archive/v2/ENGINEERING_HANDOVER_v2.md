# SmartTourismIndex — Engineering Handover v2

> **Version note:** This is v2 of the engineering handover. The v1 document remains at `docs/v1/ENGINEERING_HANDOVER.md`. v2 reflects the full scoring model rewrite completed in Q1 2026.

---

## Executive summary

SmartTourismIndex is an offline-first Swiss tourism ranking pipeline plus website data-export layer.

Its purpose is to identify **beautiful Swiss base locations** for tourists that are:
- less overrun than obvious hotspots
- strong for 1-hour public transport access
- walkable and pleasant to stay in
- good for nature, hiking, water, scenic transport, and culture
- usable without a car
- updated from real source data rather than editorial-only content

The architecture intentionally separates:
1. raw source data (`data_raw/`)
2. offline processing / scoring (`data_processed/`)
3. lightweight website-ready export files (`data_export/`)

---

## Scoring model v2

The model was completely restructured from a 4-dimension MVP into a clean 2-layer system. See `SCORING_MODEL.md` for full weights and rationale.

### Base layer — 60% of total score
How good is this place to stay in?

| Sub-score | Weight |
|---|---|
| Anti-overtourism | 25% |
| Walkability | 20% |
| Local hiking | 20% |
| Water | 15% |
| Heritage character | 10% |
| Climate | 10% |

### Access layer — 40% of total score
What can be reached within 1 hour by public transport?

| Sub-score | Weight |
|---|---|
| Scenic transport | 30% |
| Destination pull | 30% |
| Cultural POIs | 25% |
| Major hiking regions | 15% |

**PT is the engine, not a scored dimension.** GTFS defines the reachable commune set. Strong PT automatically improves Access scores. Scoring PT separately would double-count.

---

## Full pipeline scripts

### Existing scripts (unchanged or minor updates)
- `01_setup_project.ps1`
- `02_bfs_origin_split.py`
- `03_bfs_supply_demand.py`
- `04_bfs_merge.py`
- `05_climate.py`
- `06_gtfs_access.py` — local PT strength metrics only (unchanged)
- `08_water.py` — unchanged
- `10_osm_pois.py` — unchanged (restaurants, local museums)

### Phase 1 additions (Q1 2026)
- `05b_tourism_intensity_seasonality.py` — NEW: overnights per resident (OT metric) + 12-month seasonality index

### Phase 2 additions (scoring model v2)
- `06b_gtfs_reachability.py` — NEW: per-place reachable commune list (1h PT travel)
- `06c_scenic_access.py` — NEW: scenic transport + access hiking scores
- `06d_destination_pull.py` — NEW: destination pull from reachable commune overnights
- `07_hiking.py` — UPDATED: split into local (4km) and regional (20km) radius
- `07b_walkability.py` — NEW: pedestrian path density within 500m (TLM)
- `09_heritage.py` — UPDATED: UNESCO replaced by ISOS national inventory
- `10b_cultural_access.py` — NEW: named OSM museums in reachable communes
- `11_merge_score.py` — REWRITTEN: implements 2-layer model
- `12_export_site_data.py` — UPDATED: new JSON fields (seasonality, tourism_intensity, sub-scores)

### Tool scripts (not part of main pipeline)
Located in `scripts/tools/`:
- `ExtractTLM.py` — one-time extraction of all needed layers from swissTLM3D GDB to GeoPackages
- `GetpedestrianTLM.py` — inspection tool for TLM_STRASSE OBJEKTART codes
- `InspectTLM_Access.py` — inspection tool for TLM_UEBRIGE_BAHN and TLM_HALTESTELLE codes
- `GetHeritage.py` — downloads ISOS national inventory via geo.admin.ch grid API

---

## Pipeline execution order

```
01_setup_project.ps1
02_bfs_origin_split.py
03_bfs_supply_demand.py
04_bfs_merge.py
05_climate.py
05b_tourism_intensity_seasonality.py
06_gtfs_access.py
06b_gtfs_reachability.py
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

---

## Current successful state (v2)

| Script | Output | Rows |
|---|---|---|
| BFS origin split | `bfs_origin_split.csv` | 186 |
| BFS supply/demand | `bfs_supply_demand.csv` | 186 |
| BFS merged | `bfs_merged.csv` | 186 |
| Tourism intensity + seasonality | `tourism_intensity_seasonality.csv` | 186 |
| Climate metrics | `climate_metrics.csv` | 193 |
| GTFS access metrics | `gtfs_access_metrics.json` | 193 |
| GTFS reachability | `gtfs_reachability.json` | 193 |
| Hiking metrics (local + regional) | `hiking_metrics.csv` | 193 |
| Walkability metrics | `walkability_metrics.csv` | 193 |
| Water metrics | `water_metrics.csv` | 193 |
| Heritage metrics | `heritage_metrics.csv` | 193 |
| Scenic access metrics | `scenic_access_metrics.csv` | 193 |
| Destination pull metrics | `destination_pull_metrics.csv` | 193 |
| OSM POI metrics | `osm_poi_metrics.csv` | 193 |
| Cultural access metrics | `cultural_access_metrics.csv` | 193 |
| Final place scores | `place_scores.csv` | 193 |
| Exported place detail files | `data_export/*.json` | 193 |

---

## Pre-extraction step (one-time, not in main pipeline)

Before running the main pipeline for the first time on a new machine, run `ExtractTLM.py` to extract the required layers from the large GDB into smaller GeoPackages:

```powershell
py scripts/tools/ExtractTLM.py
```

This creates `data_raw/tlm/`:
- `tlm_walkability.gpkg` — 46.8 MB (127,768 pedestrian path segments)
- `tlm_hiking.gpkg` — 140.2 MB (90,692 marked trail segments)
- `tlm_scenic_transport.gpkg` — 0.9 MB (1,614 active scenic transport lines)
- `tlm_boats.gpkg` — 0.1 MB (27 boat/ferry lines)
- `tlm_stops.gpkg` — 4.6 MB (26,488 train + boat stops)

Use `--force` to re-extract: `py scripts/tools/ExtractTLM.py --force`
TLM_STRASSE layers take ~2-3 minutes. All others are fast.

ISOS data is downloaded once via:
```powershell
py scripts/tools/GetHeritage.py
```
This saves `data_raw/isos/isos_national.geojson` (1,255 national ISOS settlements).

---

## Important engineering issues — v1 (still relevant)

### BFS placeholders
BFS CSVs contain `...` and `-`. Parsers treat them as zero.

### MeteoSwiss NetCDF handling
- `decode_times=False`
- Manual month normalization
- WGS84 → LV95 coordinate transformation
- Selection by `N` / `E`, not direct `lat` / `lon`

### BFS alias mismatches
Several commune names need aliases in `place_mapping.json`.

### Duplicate slug issue
`Moutier (BE)` and `Moutier (JU)` share the same STATPOP name. Fixed by slug `moutier-ju` for the JU version. Tourism intensity for Moutier (JU) is 0 (no BFS overnights) — treated as neutral mid-range in scoring.

### OSM layer mismatch
The OSM GeoPackage does not expose a `points` layer. Correct layer: `gis_osm_pois_free`.

---

## Important engineering issues — v2 (new)

### TLM OBJEKTART codes are integers not strings
`TLM_STRASSE.OBJEKTART` stores integer codes. Key codes:
- `5` = Fussweg (footpath)
- `7` = Trottoir (sidewalk)
- `9` = Weg (general path)
- `10` = Wanderweg (hiking trail — handled via WANDERWEGE field)

### TLM AUSSER_BETRIEB encoding is inverted
In `TLM_UEBRIGE_BAHN.AUSSER_BETRIEB`:
- `1` = **active** (keep)
- `2` = out of service (exclude)
- `999998` = unknown (exclude)

This is the opposite of what the field name implies. Filter: `AUSSER_BETRIEB == 1`.

### ISOS API — grid query required
The geo.admin.ch MapServer identify API returns empty results for Switzerland-wide bounding boxes. The solution is a grid of 30km × 30km tiles covering the full Swiss extent (LV95). `GetHeritage.py` implements this. Retrieved 1,255 features.

### ISOS quality grades not available via API
The ISOS API layer provides `siedlungskategorie` (Stadt / Kleinstadt / Dorf / Spezialfall) but not detailed quality grades. Full quality grades exist only in ISOS II vector polygons (ongoing revision, partial coverage). The pipeline uses `siedlungskategorie` as a graded proxy.

### GTFS reachability is the Access layer foundation
All four Access sub-scores filter through the per-place reachable commune list from `06b_gtfs_reachability.py`. If this script produces incorrect results, all Access scores are affected. Use Tuesday 08:00–10:00 departures as the representative time window for tourist travel.

### Spatial operations must use EPSG:2056
All buffer and distance calculations in TLM scripts must reproject place coordinates from WGS84 to EPSG:2056 (LV95) before applying metre-based buffers. Geographic distance in degrees is not valid for Swiss spatial analysis.

### Tourism intensity outliers
Zermatt (~269), Lauterbrunnen (~215), and Samnaun (~210) have extreme tourism intensity values. Apply 99th percentile clip before min-max normalisation to prevent these outliers from compressing the rest of the scale.

---

## swissTLM3D layers — current usage

| Layer | Used for | Script |
|---|---|---|
| `TLM_FLIESSGEWAESSER` | Water (rivers) | `08_water.py` |
| `TLM_STEHENDES_GEWAESSER` | Water (lakes) | `08_water.py` |
| `TLM_STRASSE` (WANDERWEGE > 0) | Local + regional hiking | `07_hiking.py` |
| `TLM_STRASSE` (OBJEKTART 5,7,9) | Walkability | `07b_walkability.py` |
| `TLM_UEBRIGE_BAHN` | Scenic transport | `06c_scenic_access.py` |
| `TLM_SCHIFFFAHRT` | Boat lines | `06c_scenic_access.py` |
| `TLM_HALTESTELLE` | Train + boat stops | `06c_scenic_access.py` |

### Future TLM candidates
- `TLM_SIEDLUNGSNAME_ZENTRUM` — walkability center detection
- `TLM_EISENBAHN` (MUSEUMSBAHN attribute) — museum railway filter
- `TLM_FREIZEITAREAL` — if leisure scoring is added later

---

## Key design decisions (v2)

### UNESCO removed
UNESCO was a binary flag affecting only 6–8 communes. It created a cliff effect — UNESCO = high score, everything else = zero. Replaced by ISOS national inventory (1,255 settlements, graded by category). This distributes heritage credit broadly across Switzerland.

### PT strength not scored
PT is the engine that defines what is reachable — it powers Access but is not scored independently. Strong PT automatically shows up in better Access sub-scores (more reachable communes, more scenic transport, etc.).

### Restaurants info-only
OSM restaurant counts are too city-biased for fair scoring. Cities always win. Restaurants are shown in the place detail view as info but excluded from the score.

### Accommodation readiness info-only
All 186 communes in the dataset already have 3+ hotels (the BFS threshold that defines the dataset). More beds ≠ better base. Removed from scoring.

### Seasonality info-only
Seasonal volatility is shown as a detail widget (12-bar indexed chart) but not scored. A highly seasonal place is not necessarily worse — it may be spectacular in its peak season.

### OT as primary Base signal
Anti-overtourism carries the highest weight in Base (25%) because it is the index's core USP — finding places with high quality and low pressure. Data source: BFS overnights ÷ STATPOP resident population 2024. Validated against EU Commission formula and Watson/BFS Swiss media reporting (Zermatt: 269, Lauterbrunnen: 215, matching published figures exactly).

---

## Operational guidance

- Keep large source files in `data_raw/` — do not commit to GitHub
- Do not manually edit `data_export/` JSON files — always regenerate via `12_export_site_data.py`
- Run `ExtractTLM.py` and `GetHeritage.py` once after fresh checkout before pipeline
- Use `run_smart_tourism_pipeline_skip.ps1` during development
- `place_mapping.json` alias changes require a full pipeline rerun (clear `data_processed/` and `data_export/`)
- `places_master.csv` changes require full pipeline rerun

---

## Sanity checks after updates

Verify after every full pipeline run:
- 193 rows in `place_scores.csv`, no NaN values
- 193 JSON files in `data_export/`
- Each JSON has `seasonality`, `tourism_intensity`, and `scores.base` + `scores.access`
- Zermatt, Lauterbrunnen, Interlaken rank LOW (high OT penalty)
- Top 10 not dominated by places near Zurich (destination pull balanced by OT)
- Bellinzona: moderate-high rank (ISOS heritage + Centovalli scenic transport, moderate OT)
- Rural German-Swiss towns with good hiking and low tourism rank higher than MVP model
