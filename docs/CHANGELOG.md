# SmartTourismIndex — Changelog

Append-only version history. One block per release. See `docs/SCORING_MODEL.md` for current weights and formulas.

---

## v5 — April 2026

### Scoring changes
- **Weight rebalance:** Anti-overtourism 25% → 30%, Walkability 20% → 10%, Heritage 10% → 15%
- **ISOS buffer:** 2km → 4km — fixes heritage misses for cities where the ISOS centroid is distant from the municipality coordinate (e.g. Schaffhausen Altstadt vs. administrative centre)

### Walkability rewrite
- **Source changed:** TLM_STRASSE OBJEKTART 5/7/9 at 500m → OSM `gis_osm_roads_free` fclass `pedestrian` + `living_street` at 3km
- **Reason:** TLM does not tag alpine resort streets as pedestrian. OSM tags reflect actual car-free environments. Zermatt now correctly scores 18,110m; Arosa/Davos remain 0 (genuinely not tagged pedestrian in OSM)

### Water scoring fix
- **Lake geometry:** TLM_STEHENDES_GEWAESSER stores outlines as closed LineStrings, not filled Polygons. Added `_polygonize_lakes()` using `shapely.ops.polygonize(unary_union(...))`. Result: 43,204 boundary lines → 19,108 lake polygons. All lake areas were 0 before this fix.
- **Lake area cap:** `min(lake_area, 1,000,000 m²)` per buffer. Prevents large-lake places (Collina d'Oro, Ingenbohl) from dominating the ranking with a 100× advantage.

### Data corrections
- **Schaffhausen coordinate:** 47.722581, 8.659868 → 47.6963, 8.6337 (municipality centroid was 3.4km north of Altstadt; corrected to Bahnhof/Altstadt area). Heritage score: 0 → 100.

### Repository
- **`.gitignore` added:** `data_raw/` and `data_processed/sbbapi/` excluded from tracking

### Website
- Institutional tone pass across index.html, about.html, faq.html
- FAQ questions updated, About section revised
- CSS fix: `.ranking-controls` and `.filters` flex-direction rules moved inside `@media (max-width: 600px)` block
- CSS fix: `.detail-actions` given explicit `flex-direction: row; flex-wrap: wrap`

### Results (v5 pipeline run)
- 184 places scored, 1 excluded (Monteceneri)
- #1 Emmetten NW 69.5 | #2 Chur GR 68.3 | #3 Beckenried NW 67.1
- Schaffhausen: rank 55, total 55.98, heritage 100.0
- Bottom: Zermatt 19.2, Samnaun 12.0

---

## v4 — March/April 2026

### Scoring changes
- **Water metric rewrite:** Raw TLM feature count replaced by `water_equiv_2km_m2` = lake polygon area + river length × BREITENKLASSE width. Fixes systematic underrating of lakeside towns (a large lake = 1 polygon = 1 feature, while an alpine stream-heavy area = hundreds of short segments).

### Bug fixes
- `exclude.json` location corrected: `metadata/` → `scripts/pipeline/`

### Website
- All four pages live: index.html, methodology.html, about.html, contact.html
- Bar label width fix (ACCESS SCORE vs BASE SCORE track alignment)
- Expanded card: ISOS tag, Tourism Pressure label, seasonal chart, nearby highlights

---

## v3 — March 2026

### Architecture
- SBB API reachability matrix added (`data_processed/sbbapi/`)
- Access layer reachable commune set built from 1h PT travel time
- Place universe expanded to 184 scored + 1 excluded = 185 pipeline output, 184 exported

### New scripts
- `06b_gtfs_reachability.py` — SBB API reachable commune list per place
- `06c_scenic_access.py` — scenic transport + boat access within 14km
- `06d_destination_pull.py` — destination pull from reachable overnights
- `10b_cultural_access.py` — named OSM museums in reachable communes

### Scoring changes
- Access layer restructured: Scenic transport 30%, Destination pull 30%, Cultural access 25%, Access hiking 15%
- Heritage: UNESCO binary flag replaced by ISOS national inventory (1,255 settlements, graded 4 categories)

---

## v2 — Q1 2026

### Architecture rewrite
- 4-dimension MVP model replaced by 2-layer system: Base (60%) + Access (40%)
- PT is the engine, not a scored dimension

### Base layer introduced (6 sub-scores)
- Anti-overtourism: BFS overnights ÷ STATPOP residents, 99th percentile clip, inverted
- Walkability: TLM_STRASSE OBJEKTART 5/7/9, 500m buffer
- Local hiking: TLM WANDERWEGE 1/2/3, 4km buffer
- Water: TLM lakes + rivers, 2km buffer (feature count, later replaced in v4)
- Heritage: ISOS national inventory
- Climate: MeteoSwiss JJA normals

### New pipeline scripts
- `05b_tourism_intensity_seasonality.py`
- `07b_walkability.py`
- `11_merge_score.py` (rewrite)
- `12_export_site_data.py` (updated)

### Design decisions
- Restaurants: info-only (city-biased, removed from scoring)
- Accommodation: info-only (all places already meet BFS threshold)
- Seasonality: info-only (shown as 12-month widget, not scored)

---

## v1 — Early 2026

Initial build. 4-dimension MVP: Base quality 25%, Access value 35%, Practical comfort 20%, Anti-overtourism 20%. Real Swiss datasets connected. Pipeline runs end-to-end. Archived in `docs/archive/v2/`.
