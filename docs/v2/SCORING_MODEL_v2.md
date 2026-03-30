# SmartTourismIndex — Scoring Model v2

> **Version note:** This is v2. The v1 document remains at `docs/v1/SCORING_MODEL.md`. v2 replaces the 4-dimension MVP model with a clean 2-layer architecture based on validated public data sources.

---

## Philosophy

The model answers one question: **where is the best place to base myself for a Swiss trip?**

Not: where is the most famous place. Not: where is the most beautiful destination. But: which place gives me the best combination of a comfortable stay and rich access to day trips — without the crowds.

Two layers. Six and four sub-scores. Pure data, no editorial judgment.

---

## Top-level structure

| Layer | Weight | Question answered |
|---|---|---|
| **Base** | 60% | Is this a good place to sleep, walk around, and spend an evening? |
| **Access** | 40% | What significant day trips can I do from here within 1 hour by PT? |

**PT (public transport) is the engine, not a scored dimension.** GTFS defines the reachable commune set for each place. Strong PT automatically improves Access scores. Scoring PT separately would double-count.

---

## Base layer — 60%

*A walkable, unhurried place with local character, water nearby, trails from the doorstep, and good weather.*

Not a suburb. Not a ghost village. Not Lucerne in August.

| Sub-score | Weight within Base | Data source | Radius |
|---|---|---|---|
| Anti-overtourism | **25%** | BFS overnights ÷ STATPOP residents 2024 | Commune level |
| Walkability | **20%** | swissTLM3D `TLM_STRASSE` OBJEKTART (5=Fussweg, 7=Trottoir, 9=Weg) WANDERWEGE=0 | 500m buffer |
| Local hiking | **20%** | swissTLM3D `TLM_STRASSE` WANDERWEGE (1=yellow, 2=mountain, 3=alpine) | 4km buffer |
| Water | **15%** | swissTLM3D `TLM_STEHENDES_GEWAESSER` + `TLM_FLIESSGEWAESSER` proximity | Local |
| Heritage character | **10%** | ISOS national inventory — 1,255 settlements, graded by `siedlungskategorie` | 2km buffer |
| Climate | **10%** | MeteoSwiss summer normals (Jun–Aug temp, sunshine, precipitation) | Grid point |

### Sub-score details

**Anti-overtourism (25%)**

Formula: `tourism_intensity = annual_overnights_2024 / resident_population_2024`

This is the EU Commission standard indicator for tourism pressure, used in Swiss media (Watson, BFS) under the term *Tourismusintensität*.

Scoring: inverted and normalised — higher intensity = more pressure = lower OT score. Clip at 99th percentile before normalising to prevent extreme outliers (Zermatt: 269, Lauterbrunnen: 215) from collapsing the rest of the scale.

Data: BFS `px-x-1003020000_101` (2024 overnights) + BFS STATPOP `px-x-0102010000_101` (2024 resident population).

**Walkability (20%)**

Metric: total length in metres of pedestrian-accessible paths within 500m of the place anchor point.

Filter: `OBJEKTART IN (5, 7, 9)` AND `WANDERWEGE IN (None, 0)` — excludes hiking trails that pass through towns.

Scoring: min-max normalised across 193 places.

swissTLM3D is the national topographic survey — best possible source for Switzerland. OSM footway data was considered but TLM is authoritative and already in the pipeline.

**Local hiking (20%)**

Metric: total length in metres of marked hiking trails within 4km of the place anchor point.

Filter: `WANDERWEGE IN (1, 2, 3)` — yellow Wanderweg (1), mountain Bergwanderweg (2), alpine Alpinwanderweg (3).

The 4km radius represents trails starting from or very close to the town — what you can walk to from your hotel. Larger trail regions (Bernese Oberland, Engadin, etc.) reachable by PT are captured in the Access layer.

Scoring: min-max normalised.

**Water (15%)**

Proximity to lakes and rivers. Already implemented and validated in `08_water.py`. Best data quality in the model — swissTLM3D national survey is authoritative and complete.

A size threshold on lakes (minimum area) is recommended to filter out drainage ditches — large lakes vs small ponds represent different tourist values.

**Heritage character (10%)**

Presence of ISOS-listed settlements within 2km of the anchor point. ISOS (Bundesinventar der schützenswerten Ortsbilder der Schweiz von nationaler Bedeutung) is the federal inventory of nationally significant Swiss townscapes.

Graded by `siedlungskategorie`:

| Category | Score |
|---|---|
| Stadt | 1.0 |
| Kleinstadt/Flecken | 1.0 |
| Dorf / village / villaggio | 0.7 |
| Spezialfall / cas particulier / Sonderfall | 0.4 |
| No match within 2km | 0.0 |

If multiple ISOS entries within 2km, take the highest score.

Why ISOS instead of UNESCO: UNESCO covers only 6–8 Swiss communes and creates a binary cliff. ISOS covers 1,255 settlements with graded quality. Bellinzona's castles still score high (Kleinstadt). Stein am Rhein, Murten, Gruyères, Rapperswil — all receive appropriate credit.

**Climate (10%)**

Summer climate normals from MeteoSwiss (Jun–Aug). Moderate differentiator across Swiss communes — most places are "fine for summer tourism." Ticino and Valais benefit. Already implemented in `05_climate.py`.

### What is shown but NOT scored in Base

| Field | Why info-only |
|---|---|
| Restaurant count (OSM, 2km) | OSM density too city-biased — cities always win |
| Accommodation count (BFS) | All 186 communes have 3+ hotels (dataset filter) — more beds ≠ better base |
| Seasonality widget | Seasonal pattern is useful context, not a quality signal |
| Tourism intensity (raw number) | Shown as absolute figure alongside OT score |

---

## Access layer — 40%

*What significant day trips can be made from this base within 1 hour by PT?*

Significant = would appear on a Swiss top-100 destinations list. A cable car to the Alps. A lake boat trip. A major museum. The Rhine Falls. Not a local swimming pool.

**The reachable commune set** is computed once per place by `06b_gtfs_reachability.py` using the Swiss GTFS feed (Tuesday 08:00–10:00 departures, 60-minute travel time, minimum 3-minute transfers). All four Access sub-scores filter through this set.

| Sub-score | Weight within Access | Data source | Filter |
|---|---|---|---|
| Scenic transport | **30%** | swissTLM3D `TLM_UEBRIGE_BAHN` + `TLM_SCHIFFFAHRT` | Active lines in reachable communes |
| Destination pull | **30%** | BFS annual overnights of reachable communes | Sum of reachable commune overnights |
| Cultural POIs | **25%** | OSM `gis_osm_pois_free` fclass=museum, named only | Named museums in reachable communes |
| Major hiking regions | **15%** | swissTLM3D `TLM_STRASSE` WANDERWEGE trails | Trail length in reachable communes, 20km radius |

### Sub-score details

**Scenic transport (30%)**

Count of active scenic transport infrastructure reachable within 1h PT:
- Gondelbahn (gondola) — OBJEKTART 2
- Luftseilbahn (aerial cable car) — OBJEKTART 1
- Standseilbahn (funicular) — OBJEKTART 0
- Zahnradbahn (cogwheel/rack railway) — OBJEKTART 5
- Kabinenbahn (cabin ropeway) — OBJEKTART 7
- Boat/ferry lines (all `TLM_SCHIFFFAHRT`)

**Excluded:** Sesselbahn (chairlift, OBJEKTART 3) and Skilift (OBJEKTART 4) — ski infrastructure only, no scenic tourist value in summer.

Filter: `AUSSER_BETRIEB == 1` (active). Note: in TLM encoding, `1` = active, `2` = out of service.

Gondola/cable cars are included regardless of summer operation — infrastructure presence is the signal. A gondola that doesn't run in summer still indicates a mountain excursion destination.

Boats weighted at 0.5× compared to mountain transport — slower, more seasonal, but still meaningful access.

Scoring: min-max normalised.

**Destination pull (30%)**

Sum of annual BFS hotel overnights for all PT-reachable communes (excluding the base place itself), log-transformed to reduce the outsized effect of places near Zurich/Lucerne.

This is the coldest possible signal: if millions of people sleep somewhere, it is by definition a destination worth reaching. No editorial curation needed — visitors curate it themselves.

Note for future refinement: 30-minute reachability may be tested as an additional signal. A place 30 minutes from a major hub has another 30 minutes of secondary access from there — potentially very strong.

**Cultural POIs (25%)**

Count of named museums in reachable communes from OSM. Filter: `fclass = 'museum'` AND `name IS NOT NULL AND name != ''`. Cap at 20 to prevent major cities from dominating.

BFS Museumsstatistik (visitor counts per museum) was evaluated but individual museum visitor counts are not publicly available due to data protection for smaller institutions. OSM named museums is the best available open proxy.

**Major hiking regions (15%)**

Total trail length (metres) of marked hiking trails within 20km of all reachable commune anchor points. This captures "can I reach a proper hiking region in 1 hour?" — not the local forest walk (that's Base), but Bernese Oberland, Engadin, Ticino valleys, Wallis.

Scoring: min-max normalised.

---

## Total score calculation

```
base_score = (
    ot_score           × 0.25 +
    walkability_score  × 0.20 +
    local_hiking_score × 0.20 +
    water_score        × 0.15 +
    heritage_score     × 0.10 +
    climate_score      × 0.10
)

access_score = (
    scenic_score           × 0.30 +
    destination_pull_score × 0.30 +
    cultural_access_score  × 0.25 +
    access_hiking_score    × 0.15
)

total_score = base_score × 0.60 + access_score × 0.40
```

All sub-scores normalised 0–1 before weighting. Missing values filled with median of 193 places.

---

## What was removed from v1

| Removed | Why |
|---|---|
| UNESCO binary flag | Covered only 6–8 communes. Binary cliff. Replaced by ISOS (1,255 settlements, graded). |
| PT strength as scored dimension | PT defines the reachable set — scoring it separately double-counts. |
| Accommodation readiness | All communes already pass minimum threshold. More beds ≠ better base. |
| Diversity bonus | Skipped for v2 — adds complexity, marginal value. |
| 4-dimension structure (Base/Access/Comfort/OT) | Comfort merged into Base; OT is now the strongest Base signal. |
| Hiddenness / raw overnight count | Replaced by tourism intensity (overnights ÷ residents). |

---

## Implementation notes

**Normalisation:** min-max across all 193 places for continuous metrics. Exception: heritage uses fixed scale (0, 0.4, 0.7, 1.0) based on ISOS category.

**Missing data:** if any sub-score is missing for a place, use median of 193 places. Log a warning. Never drop a place.

**OT outlier clipping:** tourism_intensity clipped at 99th percentile before normalisation. Without clipping, Zermatt (269) and Lauterbrunnen (215) compress all other places into a narrow band.

**Coordinate systems:** all spatial buffer/distance operations in EPSG:2056 (LV95). Place coordinates in `places_master.csv` are WGS84 — reproject before buffering.
