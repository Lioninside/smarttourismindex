# SmartTourismIndex — Scoring Model v3

> **Version history:** v1 → 4-dimension MVP. v2 → 2-layer rewrite, ISOS replaces UNESCO. v3 → SBB API reachability replaces GTFS, 14km radius for Access spatial scoring, 184 places after Monteceneri exclusion, BFS script fixes.
> Previous versions archived at `docs/v1/` and `docs/v2/`.

---

## Philosophy

The model answers one question: **where is the best place to base myself for a Swiss trip?**

Two layers. Six and four sub-scores. Pure data, no editorial judgment.

---

## Top-level structure

| Layer | Weight | Question answered |
|---|---|---|
| **Base** | 60% | Is this a good place to sleep, walk around, and spend an evening? |
| **Access** | 40% | What significant day trips can I do from here within 1 hour by PT? |

**PT is the engine, not a scored dimension.** The SBB API defines the reachable commune set. Strong PT automatically improves Access scores.

---

## Place list

**184 active places** in `metadata/places_master.csv`.

Excluded via `metadata/exclude.json`:
- `monteceneri` — merger commune, ~2,900 overnights, not a valid tourist base.

---

## Base layer — 60%

| Sub-score | Weight | Data source | Radius |
|---|---|---|---|
| Anti-overtourism | **25%** | BFS overnights ÷ STATPOP residents 2024 | Commune level |
| Walkability | **20%** | swissTLM3D TLM_STRASSE OBJEKTART (5,7,9) | 500m buffer |
| Local hiking | **20%** | swissTLM3D TLM_STRASSE WANDERWEGE (1,2,3) | 4km buffer |
| Water | **15%** | swissTLM3D lakes + rivers | Local |
| Heritage character | **10%** | ISOS national inventory, graded | 2km buffer (EPSG:2056) |
| Climate | **10%** | MeteoSwiss Jun–Aug normals | Grid point |

### Anti-overtourism (25%)

`tourism_intensity = annual_overnights_2024 / resident_population_2024`

EU Commission standard indicator. Inverted, clipped at 99th percentile, min-max normalised. Validated: Zermatt 268.9, Lauterbrunnen 214.7, Grindelwald 210.3.

### Walkability (20%)

Total metres of pedestrian paths within 500m. OBJEKTART IN (5,7,9) AND WANDERWEGE = 0/null.

### Local hiking (20%)

Total metres of marked hiking trails within 4km. WANDERWEGE IN (1,2,3).

### Water (15%)

Equivalent water area within 2km of the place anchor (EPSG:2056 buffer).

**Metric: `water_equiv_2km_m2`** (output of `08_water.py`)

```
water_equiv_2km_m2 = Σ clipped lake polygon area (m²)
                   + Σ (clipped river length (m) × BREITENKLASSE width)
```

River width by TLM `BREITENKLASSE` attribute:

| Class | Width range | Width used |
|---|---|---|
| 1 | < 1 m | 0.5 m |
| 2 | 1–5 m | 3.0 m |
| 3 | 5–15 m | 10.0 m |
| 4 | 15–50 m | 30.0 m |
| 5 | > 50 m | 75.0 m |
| missing | — | 3.0 m (fallback) |

Rationale: the old feature-count approach (raw TLM intersections) heavily underrated lakeside towns — Lake Thun is one large polygon while an alpine stream-heavy area generates hundreds of short river segments. Area-equivalent scoring gives proportional weight to large lakes, wide rivers (Aare, Rhine, Rhone), and correctly discounts long-but-narrow alpine streams.

Scoring: `water_equiv_2km_m2` min-max normalised across 184 places.

**Requires updated `water_metrics.json`** — old files contain only `water_features_2km`. Rerun `08_water.py` before `11_merge_score.py` on any existing installation.

### Heritage character (10%)

ISOS national inventory (1,255 settlements) within 2km. Coordinates are LV95 — use `set_crs(2056)` not `to_crs`. Reproject places WGS84 → EPSG:2056 before buffering.

| Category | Score |
|---|---|
| Stadt / Kleinstadt/Flecken | 1.0 |
| Dorf / village / villaggio / Verstädtertes Dorf | 0.7 |
| Spezialfall / cas particulier / Sonderfall / Agglomeration | 0.4 |
| Unrecognised | 0.5 |
| No match within 2km | 0.0 |

### Climate (10%)

MeteoSwiss Jun–Aug temperature, sunshine, precipitation normals.

### Info-only (not scored)

Restaurant count (OSM), accommodation (BFS), seasonality widget, tourism intensity raw number.

---

## Access layer — 40%

| Sub-score | Weight | Data source | Method |
|---|---|---|---|
| Scenic transport | **30%** | TLM_UEBRIGE_BAHN + TLM_SCHIFFFAHRT | 14km radius |
| Destination pull | **30%** | BFS overnights of reachable communes | SBB API set |
| Cultural POIs | **25%** | OSM named museums | 14km radius |
| Major hiking regions | **15%** | TLM hiking trails, regional | 20km from hiking_metrics |

### SBB API reachability

Authoritative file: `data_processed/sbbapi/sbbAPI_reachability.json`

4-step architecture:
1. **Curated master** — 184 places with manually validated SBB station IDs
2. **Hub assignment** — one representative PT node per place (main station or central hub)
3. **100km prefilter** — only communes within 100km air distance evaluated
4. **API verification** — real timetable queries; ≤ 60min connections retained

GTFS-based alternative (`06b_gtfs_reachability.py`) achieved only 27.7% agreement with SBB API due to calendar_dates.txt filtering issues — deprecated.

### Scenic transport (30%)

TLM active scenic lines (AUSSER_BETRIEB = 1) within **14km** of place anchor (EPSG:2056 buffer).

Included: Gondelbahn (2), Luftseilbahn (1), Standseilbahn (0), Zahnradbahn (5), Kabinenbahn (7), all boats.
Excluded: Sesselbahn (3), Skilift (4).
Boats weighted 0.5×. Deduplicated by NAME.

**Why 14km radius:** previous commune-center union buffers missed gondola stations between communes. 14km captures infrastructure regardless of commune boundaries. Validated: 14 places with zero coverage are all geographically justified (flat lowland or isolated valleys).

### Destination pull (30%)

Sum of BFS overnights for SBB-reachable communes (excluding base place). Log-transformed, min-max normalised.

### Cultural POIs (25%)

Named OSM museums within **14km** (OSM reprojected to EPSG:2056). Cap at 20. Min-max normalised. BFS Museumsstatistik evaluated but individual counts not publicly available.

### Major hiking regions (15%)

`regional_hiking_score` from `hiking_metrics.json` (20km radius trail metres).

---

## Score calculation

```python
base_score = (
    ot_score           * 0.25 +
    walkability_score  * 0.20 +
    local_hiking_score * 0.20 +
    water_score        * 0.15 +
    heritage_score     * 0.10 +
    climate_score      * 0.10
)

access_score = (
    scenic_score           * 0.30 +
    destination_pull_score * 0.30 +
    cultural_access_score  * 0.25 +
    access_hiking_score    * 0.15
)

total_score = base_score * 0.60 + access_score * 0.40
```

All sub-scores 0–1. Missing values → median. No places dropped.

---

## Known risks and limitations

### Base risks

**OT minimum activity threshold:** Places with very low overnight stays score near-perfect on OT but may lack accommodation infrastructure. Monteceneri (2,893 overnights) excluded. Other borderline cases may exist — monitor top 10 after each run.

**Walkability anchor sensitivity:** 500m buffer centred on station coordinates, not always the town center pedestrian core.

**ISOS quality grades partial:** Only `siedlungskategorie` available via API. Cannot distinguish a well-preserved village from a degraded one within the same category.

### Access risks

**SBB hub selection:** Wrong hub = wrong reachability graph. Station IDs manually validated but may drift with SBB infrastructure changes. Regenerate `sbbAPI_reachability.json` annually (December timetable).

**14km ignores mountains:** Splügen–Vals is the documented case: 12km straight line, mountain between, 2h33min travel. The Vals gondola incorrectly counts for Splügen's scenic score. No fix without topographic awareness or per-pair PT verification.

**Destination pull currency:** `sbbAPI_reachability.json` reflects the timetable at generation time. Regenerate with each December timetable update.

**OSM museum coverage:** Mild urban bias — rural areas may have fewer mapped museums.

---

## Changes from v2 to v3

| Item | v2 | v3 |
|---|---|---|
| Reachability source | GTFS (27.7% accuracy) | SBB API (validated) |
| Scenic/cultural spatial method | Commune-center union buffers | 14km radius from place anchor |
| Place count | 185 | 184 (Monteceneri excluded) |
| ISOS coordinate handling | Bug — haversine on LV95 | Fixed — EPSG:2056 metre buffers |
| Water GeoPackages | Missing | `tlm_rivers.gpkg` + `tlm_lakes.gpkg` |
| Water scoring metric | Raw feature count | Area-equivalent m² (lake area + river length × BREITENKLASSE width) |
| BFS column names | English (broken) | German (fixed) |
| BFS filenames | Hardcoded dates | Wildcard glob |
| place_mapping.json | Basic aliases | Canton-qualified BFS name aliases |
| Excluded places | None | `scripts/pipeline/exclude.json` |
| Score output format | `subscores` only | `scores.base`, `scores.access`, `scores.sub.*` |
