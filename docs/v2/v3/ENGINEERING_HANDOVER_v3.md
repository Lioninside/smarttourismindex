# SmartTourismIndex — Engineering Handover v3

> **Version history:** v1 → initial build. v2 → 2-layer scoring rewrite, ISOS, full pipeline. v3 → SBB API reachability, water scoring overhaul, website frontend complete.
> Previous versions archived at `docs/v1/` and `docs/v2/`.

---

## Executive summary

SmartTourismIndex is an offline-first Swiss tourism ranking pipeline plus a website data-export layer.

Architecture separates:
1. Raw source data (`data_raw/`) — not committed to GitHub
2. Offline processing and scoring (`data_processed/`)
3. Website-ready export (`data_export/`)
4. Static website (`website/`)

184 Swiss places in the current edition. Monteceneri excluded via `scripts/pipeline/exclude.json`.

---

## What changed in v3

### Reachability: GTFS replaced by SBB API

`06b_gtfs_reachability.py` (GTFS-based) produced only 27.7% agreement with verified SBB connections due to `calendar_dates.txt` filtering issues. Replaced by SBB API output.

Authoritative reachability file: `data_processed/sbbapi/sbbAPI_reachability.json`
- 184 origin places, each with a list of reachable place slugs within 60 minutes
- Generated externally via SBB API with 100km geographic prefilter
- Regenerate annually after December timetable update

`06b_gtfs_reachability.py` remains on disk but is not run in the main pipeline.

### Water scoring: feature count replaced by area-equivalent

The old approach counted raw TLM feature intersections within a 2km buffer. This severely underrated lakeside towns (Lake Thun = 1 polygon) relative to alpine stream-heavy areas (hundreds of short river line segments).

New metric: **`water_equiv_2km_m2`** (written to `water_metrics.json`)

```
water_equiv_2km_m2 = lake_polygon_area_clipped (m²)
                   + Σ (river_segment_length_clipped × BREITENKLASSE_width)
```

`BREITENKLASSE` is the TLM river width class attribute:

| BREITENKLASSE | Meaning | Width used |
|---|---|---|
| 1 | < 1 m | 0.5 m |
| 2 | 1–5 m | 3.0 m |
| 3 | 5–15 m | 10.0 m |
| 4 | 15–50 m | 30.0 m |
| 5 | > 50 m | 75.0 m |
| missing | fallback | 3.0 m |

This correctly weights wide rivers (Aare through Bern, Rhine through Basel) and large lakes (Lake Thun, Lake Lucerne) against narrow alpine streams. A long thin mountain brook at class 1–2 contributes near-zero area even if long.

`11_merge_score.py` reads `water_equiv_2km_m2` for the water sub-score (15% of Base).

Old fields `water_features_2km` and `water_features_10km` (raw feature counts) remain in `water_metrics.json` for diagnostics but are no longer used in scoring.

### Place count: 185 → 184

`monteceneri` excluded. Reason: merger commune, ~2,893 overnights, not a valid tourist base. Managed via `scripts/pipeline/exclude.json` — applied in `11_merge_score.py` before scoring and in `12_export_site_data.py` before export.

**Important:** `exclude.json` was accidentally deleted during development and must be recreated if missing:
```json
["monteceneri"]
```

### Scenic and cultural spatial method: commune buffers → 14km radius

v2 used a union of commune-centre buffers from the reachable set. v3 uses a direct 14km radius from the place anchor point (EPSG:2056) for scenic transport and cultural POI scoring. Validated: 14 places with zero coverage are geographically justified.

### Score output format change

`11_merge_score.py` now outputs a `scores` key alongside the legacy `subscores` key:

```json
"scores": {
  "total": 66.0,
  "base":  64.0,
  "access": 69.0,
  "sub": {
    "anti_overtourism": 78.4,
    "walkability": 62.1,
    "local_hiking": 71.3,
    "water": 55.2,
    "heritage": 100.0,
    "climate": 61.0,
    "scenic_transport": 80.0,
    "destination_pull": 65.3,
    "cultural_access": 55.0,
    "access_hiking": 72.1
  }
}
```

`12_export_site_data.py` exports `scores` to the site. `subscores` (legacy) is popped before export.

---

## Full pipeline scripts — current state

### Active pipeline (run in order)
```
scripts/pipeline/02_bfs_origin_split.py
scripts/pipeline/03_bfs_supply_demand.py
scripts/pipeline/04_bfs_merge.py
scripts/pipeline/05_climate.py
scripts/pipeline/05b_tourism_intensity_seasonality.py
scripts/pipeline/06_gtfs_access.py
scripts/pipeline/06c_scenic_access.py
scripts/pipeline/06d_destination_pull.py
scripts/pipeline/07_hiking.py
scripts/pipeline/07b_walkability.py
scripts/pipeline/08_water.py
scripts/pipeline/09_heritage.py
scripts/pipeline/10_osm_pois.py
scripts/pipeline/10b_cultural_access.py
scripts/pipeline/11_merge_score.py
scripts/pipeline/12_export_site_data.py
```

### Not in main pipeline (kept for reference)
- `scripts/pipeline/06b_gtfs_reachability.py` — GTFS reachability (deprecated, 27.7% accuracy)

### Runner scripts
- `scripts/run_smart_tourism_pipeline.ps1` — full run
- `scripts/run_smart_tourism_pipeline_skip.ps1` — development run (skips slow scripts)

Both use `((Get-Date) - $t).TotalSeconds` for elapsed time. Note: `Get-Date - $t` (without parentheses) fails in PowerShell — the `-` is parsed as a parameter name.

### Tool scripts (one-time, not in main pipeline)
Located in `scripts/tools/`:
- `ExtractTLM.py` — extracts TLM layers from GDB to GeoPackage. Run once per machine.
- `GetHeritage.py` — downloads ISOS inventory via geo.admin.ch grid API. Run once.
- `GetpedestrianTLM.py` — inspection tool for TLM OBJEKTART codes
- `InspectTLM_Access.py` — inspection tool for TLM scenic transport codes

---

## Data files — current outputs

| Script | Output file | Rows |
|---|---|---|
| 02–04 BFS | `data_processed/bfs/bfs_merged.csv` | 186 |
| 05b intensity | `data_processed/tourism_intensity_seasonality.csv` | 184 |
| 05 climate | `data_processed/climate/climate_metrics.csv` | 193 |
| 06c scenic | `data_processed/scenic_access_metrics.json` | 193 |
| 06d dest pull | `data_processed/destination_pull_metrics.json` | 184 |
| 07 hiking | `data_processed/hiking/hiking_metrics.json` | 193 |
| 07b walkability | `data_processed/walkability_metrics.json` | 193 |
| 08 water | `data_processed/water/water_metrics.json` | 193 |
| 09 heritage | `data_processed/heritage/heritage_metrics.json` | 193 |
| 10 OSM POIs | `data_processed/osm/osm_poi_metrics.json` | 193 |
| 10b cultural | `data_processed/cultural_access_metrics.csv` | 193 |
| 11 merge | `data_processed/final/place_scores.json` | 184 |
| 12 export | `data_export/places-index.json` + `data_export/places/*.json` | 184 |
| SBB API | `data_processed/sbbapi/sbbAPI_reachability.json` | 184 keys |

---

## Engineering issues — new in v3

### Water `water_equiv_2km_m2` requires `08_water.py` rerun

The new water scoring field (`water_equiv_2km_m2`) is only present after running the updated `08_water.py`. Old `water_metrics.json` files contain only `water_features_2km`. `11_merge_score.py` falls back to 0 if the field is absent and logs a warning — always rerun `08_water.py` before `11_merge_score.py`.

### `exclude.json` must exist before running pipeline

`scripts/pipeline/exclude.json` controls which places are dropped from scoring and export. If the file is missing, all places including Monteceneri are included. The file must contain at minimum:
```json
["monteceneri"]
```

### `BREITENKLASSE` may be absent for some TLM river segments

If the attribute is missing in a segment, `_river_equiv_area()` falls back to `RIVER_WIDTH_FALLBACK_M = 3.0`. The fallback is conservative — a 3m-wide stream contributes modestly but not zero.

### ISOS coordinates are LV95, not WGS84

`09_heritage.py` reads ISOS GeoJSON with LV95 coordinates. Use `set_crs(2056)` not `to_crs(2056)`. Reprojecting place anchor points from WGS84 to EPSG:2056 before buffering is required for metre-accurate results.

### Tourism intensity: high absolute overnights ≠ high pressure

The anti-overtourism score uses `overnights / resident_population`. A city like Locarno (314K overnights, ~15K residents ≈ 21 per resident) genuinely ranks as low-pressure relative to alpine resorts (Zermatt: ~270 per resident, Lauterbrunnen: ~215). This is by design and matches the EU Commission / BFS methodology.

---

## Engineering issues carried from v2

### TLM OBJEKTART codes are integers not strings
`TLM_STRASSE.OBJEKTART`: 5=Fussweg, 7=Trottoir, 9=Weg, 10=Wanderweg.

### TLM AUSSER_BETRIEB encoding is inverted
In `TLM_UEBRIGE_BAHN.AUSSER_BETRIEB`: `1` = active (keep), `2` = out of service.

### ISOS API — grid query required
geo.admin.ch MapServer returns empty results for Switzerland-wide bounding boxes. `GetHeritage.py` uses 30km × 30km grid tiles.

### Spatial operations must use EPSG:2056
All buffer and distance calculations must reproject from WGS84 to EPSG:2056 before applying metre-based buffers.

### OT outlier clipping
`tourism_intensity` clipped at 99th percentile before normalisation. Validated extremes: Zermatt 268.9, Lauterbrunnen 214.7, Grindelwald 210.3.

### BFS alias mismatches
Several commune names need aliases in `metadata/place_mapping.json`. Canton-qualified aliases required for ambiguous names.

### PowerShell elapsed time syntax
`Get-Date - $t` fails — use `((Get-Date) - $t).TotalSeconds`.

---

## Website — current state

Four-page static site in `website/`:
- `index.html` — ranking, hero, score explanation, about
- `methodology.html` — scoring methodology for non-technical readers
- `about.html` — project background, open source positioning
- `contact.html` — LinkedIn and GitHub CTAs only, no email

### Data loading
App reads from `/data_export/` at runtime:
- `places-index.json` — all places, summary scores
- `places/{slug}.json` — full detail per place (loaded on card expand)
- `coordinates.json` — lat/lon for map

Collapsed card bars read: `scores.base` → fallback `subscores.base_quality` → 0.
Expanded card reads: `scores.sub.anti_overtourism` for Tourism Pressure label.

### Tourism Pressure label thresholds (app.js)
```javascript
aot > 75 → 'LOW'
aot > 50 → 'MODERATE'
aot > 25 → 'HIGH'
else     → 'VERY HIGH'
```
`aot` is `scores.sub.anti_overtourism` (0–100, inverted — high = low pressure).

### Nearby highlights (app.js SWISS_TOP20)
31-place curated list in priority order (Zürich first, Flims last). Only places in this list AND in `detail.reachable_slugs` are shown (up to 3).

---

## Sanity checks after full pipeline run

- 184 rows in `data_export/places-index.json`
- `data_export/places/monteceneri.json` does NOT exist
- Each place detail has `scores.base`, `scores.access`, `scores.sub.anti_overtourism`
- `water_metrics.json` entries have `water_equiv_2km_m2` field
- Zermatt, Lauterbrunnen, Grindelwald: high anti-overtourism penalty, lower total scores
- Locarno: Tourism Pressure LOW is correct (21 overnights per resident)
- Spiez: `water_equiv_2km_m2` substantially higher than old feature count suggested
- Bern, Basel: strong water signal from Aare/Rhine river area

---

## Operational rules

- Never commit `data_raw/` — large GDB and raw CSV files
- Never manually edit `data_export/` — always regenerate via `12_export_site_data.py`
- `place_mapping.json` changes → full pipeline rerun required
- `places_master.csv` changes → full pipeline rerun required
- `sbbAPI_reachability.json` → regenerate annually (December timetable)
- Run `ExtractTLM.py` and `GetHeritage.py` once after fresh checkout
