# SmartTourismIndex — Data Sources v2

> **Version note:** This is v2. The v1 document remains at `docs/v1/DATA_SOURCES.md`. v2 reflects all data sources used in the scoring model v2 rewrite. UNESCO has been removed as an active source.

---

## Overview

All data sources are public, free, and official Swiss federal or open data. No editorial scoring, no surveys, no commercial APIs.

| Source | Format | Layer / Usage | Status |
|---|---|---|---|
| BFS HESTA (tourism) | CSV | OT score, destination pull, seasonality | ✅ active |
| BFS STATPOP (population) | CSV | OT score denominator | ✅ active |
| MeteoSwiss climate normals | NetCDF | Climate sub-score | ✅ active |
| Swiss GTFS | ZIP | PT reachability engine | ✅ active |
| swissTLM3D | ESRI GDB → GeoPackage | Walkability, hiking, water, scenic transport, boats | ✅ active |
| OSM / Geofabrik | GeoPackage | Restaurants (info), museums (Access) | ✅ active |
| ISOS / BAK | GeoJSON (API) | Heritage sub-score | ✅ active |
| UNESCO | JSON | — | ❌ removed (v2) |

---

## BFS HESTA — hotel tourism statistics

**Files:**
- `px-x-1003020000_101_*.csv` — monthly arrivals and overnights by commune and origin country
- `px-x-1003020000_201_*.csv` — monthly supply and demand (beds, occupancy) by commune

**Used for:**
- Annual overnights per commune → OT score numerator (tourism intensity)
- Monthly overnights (12 values per commune) → seasonality index and widget
- Accommodation count (beds, rooms) → info-only in place detail
- Destination pull → annual overnights of GTFS-reachable communes

**Download:** BFS STAT-TAB at `https://www.pxweb.bfs.admin.ch`

**Key technical notes:**
- Files use ISO-8859-1 encoding
- BFS placeholder values `...` and `-` must be treated as zero
- 2025 file has mixed German/English month names — `Juli` appears instead of `July` in some exports
- 2024 file is the primary year for OT scoring (most recent complete year)
- 186 communes with data (BFS threshold: 3+ regularly open establishments)

**Coverage:** 186 of 193 pipeline places. 7 places have no BFS data (small communes below threshold) — treated as zero overnights / neutral OT score.

---

## BFS STATPOP — resident population

**File:** `px-x-0102010000_101_*.csv`

**Used for:**
- Tourism intensity denominator: `overnights / resident_population`

**Download:** BFS STAT-TAB at `https://www.pxweb.bfs.admin.ch`

**Key technical notes:**
- ISO-8859-1 encoding
- Filter to: `Bevölkerungstyp = Ständige Wohnbevölkerung`, `Staatsangehörigkeit = Total`, `Geschlecht = Total`, `Jahr = 2024`
- Commune names in format `......XXXX Gemeindename` — strip the leading dots and number to get plain name
- 2,131 Swiss communes in file; 183 of 186 BFS tourism communes match directly by name
- 3 mismatches: `Moutier (BE)`, `Moutier (JU)` (both map to plain `Moutier` in STATPOP), `Laténa`

**Validated results (2024):**
- Zermatt: 6,099 residents, 1,640,200 overnights → intensity 268.9 (Watson reported 269 ✓)
- Lauterbrunnen: 2,331 residents, 500,405 overnights → intensity 214.7 (Watson reported 215 ✓)
- Grindelwald: 3,930 residents, 826,466 overnights → intensity 210.3 (Watson reported 210 ✓)

---

## MeteoSwiss climate normals

**Purpose:**
- Summer temperature (Jun–Aug average)
- Summer precipitation (Jun–Aug average)
- Summer sunshine (Jun–Aug hours)

**Key technical notes:**
- NetCDF format requires `decode_times=False`
- Manual month normalisation needed
- WGS84 to LV95 coordinate transformation required
- Selection by `N` / `E` grid coordinates, not direct `lat` / `lon`
- Current pipeline uses June, July, August as summer proxy

**Download:** MeteoSwiss open data portal

---

## Swiss GTFS

**File:** `data_raw/gtfs/gtfs_fp2025_20251211.zip`

**Used for:**
- Anchor stop per place (nearest station-like stop)
- Local PT strength metrics (route count, nearby stops) — info context
- **1-hour reachable commune set per place** — foundation of all Access sub-scores

**Key technical notes:**
- Large file — load `stop_times.txt`, `trips.txt`, `stops.txt` once and build indexes; never re-read in loops
- Representative time window: Tuesday departures 08:00–10:00 (normal tourist day travel)
- Minimum transfer time: 3 minutes
- Cap reachable communes at 30 per place to prevent outliers
- Fallback for places with no departures in window: geographic 40km radius

**Output files:**
- `data_processed/gtfs/gtfs_access_metrics.json` — local PT strength per place (from `06_gtfs_access.py`)
- `data_processed/gtfs/gtfs_reachability.json` — per-place list of reachable commune slugs (from `06b_gtfs_reachability.py`)

---

## swissTLM3D — national topographic landscape model

**Main file:** `data_raw/swissTLM3D_2026_LV95_LN02.gdb`

**CRS:** EPSG:2056 (CH1903+ / LV95)

All layers are extracted once via `scripts/tools/ExtractTLM.py` into `data_raw/tlm/*.gpkg` before the main pipeline runs.

### Layers in active use

**`TLM_STRASSE`** — road and path network (line geometry)

Key fields:
- `OBJEKTART` (int32): path type code
  - 5 = Fussweg (footpath) → walkability
  - 7 = Trottoir (sidewalk) → walkability
  - 9 = Weg (general path) → walkability
  - 10 = Wanderweg (hiking trail) — use WANDERWEGE field instead
- `WANDERWEGE` (int32): hiking trail classification
  - None/0 = not a hiking trail → walkability filter
  - 1 = Wanderweg (yellow, local) → hiking
  - 2 = Bergwanderweg (white-red, mountain) → hiking
  - 3 = Alpinwanderweg (white-blue-white, alpine) → hiking (not present in 2026 dataset)
- `BELAGSART` (int32): surface type (100 = paved — 99.5% of paths)
- `SHAPE_Length`: segment length in metres

Extracted to:
- `data_raw/tlm/tlm_walkability.gpkg` — 127,768 features (OBJEKTART 5,7,9 + WANDERWEGE 0/None)
- `data_raw/tlm/tlm_hiking.gpkg` — 90,692 features (WANDERWEGE 1,2,3)

**`TLM_UEBRIGE_BAHN`** — non-standard railway / lift infrastructure (line geometry)

Key fields:
- `OBJEKTART` (int32): transport type
  - 0 = Standseilbahn (funicular) ✅
  - 1 = Luftseilbahn (aerial cable car) ✅
  - 2 = Gondelbahn (gondola) ✅
  - 3 = Sesselbahn (chairlift) ❌ excluded — ski infrastructure
  - 4 = Skilift ❌ excluded — ski infrastructure
  - 5 = Zahnradbahn (cogwheel railway) ✅
  - 7 = Kabinenbahn (cabin ropeway) ✅
- `AUSSER_BETRIEB` (int32): service status — **1 = active**, 2 = out of service, 999998 = unknown
- `NAME`: line name
- `BETRIEBSBAHN`: operator flag

Extracted to: `data_raw/tlm/tlm_scenic_transport.gpkg` — 1,614 active scenic transport lines

Breakdown: Zahnradbahn 765 / Gondelbahn 363 / Standseilbahn 317 / Luftseilbahn 144 / Kabinenbahn 25

**`TLM_SCHIFFFAHRT`** — boat and ferry lines (line geometry)

All 27 lines kept (no filter). Covers all Swiss lake and river ferry routes.

Extracted to: `data_raw/tlm/tlm_boats.gpkg` — 27 features

**`TLM_HALTESTELLE`** — PT stops (point geometry)

Key fields:
- `OBJEKTART` (int32): stop type
  - 0 = Zug (train) ✅ kept
  - 1 = Schiff (boat/ship) ✅ kept
  - 2 = Bus ❌ excluded (too dense, not useful for scenic access)
  - 4 = Tram ❌ excluded
  - Note: code 3 (Uebrige_Bahn / cable car stops) does not exist in this layer — gondola proximity uses TLM_UEBRIGE_BAHN line geometry instead

Extracted to: `data_raw/tlm/tlm_stops.gpkg` — 26,488 features (23,331 boat + 3,157 train)

**`TLM_FLIESSGEWAESSER`** — rivers (line geometry) — used in `08_water.py`

**`TLM_STEHENDES_GEWAESSER`** — lakes (polygon geometry) — used in `08_water.py`

### Future TLM candidates (not yet in pipeline)

- `TLM_SIEDLUNGSNAME_ZENTRUM` — settlement center detection for walkability refinement
- `TLM_EISENBAHN` (MUSEUMSBAHN attribute) — museum railway filter for scenic transport
- `TLM_FREIZEITAREAL` — formal leisure areas (if leisure scoring added)
- `TLM_SCHUTZGEBIET` — protected natural areas (if nature park scoring added)

---

## OSM / Geofabrik GeoPackage

**File:** `data_raw/osm/osm_switzerland.gpkg`

**Layer:** `gis_osm_pois_free`

**Note:** The layer name is `gis_osm_pois_free` — not `points`. This caused a pipeline error in v1, now documented.

**Fields used:**
- `fclass` — feature class
- `name` — feature name (used as quality filter: named features only)

**Active uses:**

| fclass | Filter | Used for | Script |
|---|---|---|---|
| `restaurant` | named only | Restaurant count (info-only) | `10_osm_pois.py` |
| `museum` | named only | Local museum count (Base info) | `10_osm_pois.py` |
| `museum` | named only, in reachable communes | Cultural access score (Access) | `10b_cultural_access.py` |

**Named-only filter:** `name IS NOT NULL AND name != ''` — eliminates unmapped or poorly mapped features. Removes most noise and urban bias. A named museum in OSM is almost always a real museum.

**OSM coverage note:** Switzerland has among the highest OSM quality globally. Swiss mappers are thorough. Coverage is reliable for museums and restaurants in all 193 pipeline communes.

**Download:** Geofabrik at `https://download.geofabrik.de/europe/switzerland.html` — `switzerland-latest-free.gpkg.zip` (experimental GeoPackage, updated daily).

---

## ISOS — Bundesinventar der schützenswerten Ortsbilder

**File:** `data_raw/isos/isos_national.geojson`

**Source:** geo.admin.ch MapServer API — `ch.bak.bundesinventar-schuetzenswerte-ortsbilder`

**Publisher:** Bundesamt für Kultur (BAK)

**Content:** All 1,255 nationally significant Swiss townscapes and settlement areas

**Available fields:**
- `name` — settlement name (e.g. "Stein am Rhein", "Gruyères", "Bellinzona")
- `nummer` — ISOS settlement number (unique ID, 1–~6300 with gaps)
- `siedlungskategorie` — settlement category:
  - `Stadt` — town/city
  - `Kleinstadt/Flecken` — small town
  - `Dorf` / `village` / `villaggio` — village
  - `Spezialfall` / `cas particulier` / `Sonderfall` — special case (e.g. dispersed rural landscape, wine region)
- `kantone` — canton(s)
- `url` — link to gisos.bak.admin.ch record

**No quality grades available via API.** Detailed quality grades exist only in ISOS II vector polygons (ongoing national revision, partial coverage only). The `siedlungskategorie` field is used as a graded proxy in the scoring model.

**Download method:** Grid query of 30km × 30km tiles covering Switzerland in LV95. Direct API calls to the full Swiss bounding box return empty results. `GetHeritage.py` implements the grid approach. Retrieved 1,255 features.

**CRS:** WGS84 (GeoJSON standard). Reproject to EPSG:2056 before spatial joins.

**Update frequency:** Annual (BAK updates ISOS yearly).

---

## UNESCO (removed in v2)

**File:** `data_raw/swiss_unesco_sites.json`

**Status:** ❌ No longer used in scoring or export. File retained on disk for reference.

**Why removed:** Binary flag. Covered only 6–8 Swiss communes out of 193. Created a cliff effect — UNESCO = high score, everything else = zero. No quality gradation. Replaced by ISOS (1,255 settlements, graded). Bellinzona's UNESCO castles are still captured via ISOS (Kleinstadt/Flecken) and via OSM historic features.

---

## Data refresh schedule

| Source | Recommended refresh | Notes |
|---|---|---|
| BFS HESTA (101, 201) | Annual (after BFS annual release, ~March) | Replace files in `data_raw/bfs/`, rerun from step 02 |
| BFS STATPOP | Annual (same timing as HESTA) | Replace file in `data_raw/bfs/`, rerun from 05b |
| MeteoSwiss climate | Every 5–10 years (normals update slowly) | Replace NetCDF files, rerun 05 |
| Swiss GTFS | Annual (new timetable, December) | Replace ZIP in `data_raw/gtfs/`, rerun from 06 |
| swissTLM3D | Annual (swisstopo annual release, February) | Replace GDB, re-run `ExtractTLM.py`, rerun from 07 |
| OSM / Geofabrik | Annual or as needed | Replace GPKG, rerun 10, 10b |
| ISOS | Annual (BAK annual update) | Re-run `GetHeritage.py`, rerun 09 |
