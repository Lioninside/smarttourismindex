# SmartTourismIndex — Scoring Model v4

> **Version history:** v1 → 4-dimension MVP. v2 → 2-layer rewrite, ISOS. v3 → SBB API reachability, 14km radius, 184 places. v4 → water scoring overhaul (area-equivalent metric).
> Previous versions archived at `docs/v2/` and `docs/v2/v3/`.

---

## Architecture (unchanged from v3)

| Layer | Weight | Question |
|---|---|---|
| **Base** | 60% | Is this a good place to stay in? |
| **Access** | 40% | What can be reached within 1 hour by PT? |

PT is the engine, not a scored dimension. SBB API defines the reachable set.

---

## Base layer — 60%

| Sub-score | Weight | Data source | Radius |
|---|---|---|---|
| Anti-overtourism | **25%** | BFS overnights ÷ STATPOP residents 2024 | Commune level |
| Walkability | **20%** | swissTLM3D TLM_STRASSE OBJEKTART (5,7,9) | 500m |
| Local hiking | **20%** | swissTLM3D TLM_STRASSE WANDERWEGE (1,2,3) | 4km |
| Water | **15%** | swissTLM3D lakes + rivers — area equivalent | 2km |
| Heritage character | **10%** | ISOS national inventory, graded | 2km (EPSG:2056) |
| Climate | **10%** | MeteoSwiss Jun–Aug normals | Grid point |

### Anti-overtourism (25%)

`tourism_intensity = annual_overnights_2024 / resident_population_2024`

EU Commission / BFS standard indicator. Inverted, clipped at 99th percentile, min-max normalised.

Validated extremes: Zermatt 268.9, Lauterbrunnen 214.7, Grindelwald 210.3.

Interpretation: high raw overnights alone does not mean high pressure. Locarno (314K overnights, ~15K residents ≈ 21 per resident) correctly ranks as low-pressure relative to alpine resorts.

### Walkability (20%)

Total metres of pedestrian paths within 500m. `OBJEKTART IN (5,7,9)` AND `WANDERWEGE = 0/null`.

### Local hiking (20%)

Total metres of marked hiking trails within 4km. `WANDERWEGE IN (1,2,3)`.

### Water (15%) — updated in v4

**Metric: `water_equiv_2km_m2`**

```
water_equiv_2km_m2 = Σ clipped lake polygon area (m²)
                   + Σ (clipped river length (m) × BREITENKLASSE_width)
```

River width per TLM `BREITENKLASSE` attribute:

| Class | Range | Width used |
|---|---|---|
| 1 | < 1 m | 0.5 m |
| 2 | 1–5 m | 3.0 m |
| 3 | 5–15 m | 10.0 m |
| 4 | 15–50 m | 30.0 m |
| 5 | > 50 m | 75.0 m |
| missing | — | 3.0 m |

**Why area-equivalent replaces feature count:**

Raw TLM feature intersections created a systematic bias. A large lake (Lake Thun) is one polygon — one feature. An alpine area with many streams generates hundreds of short line segments — hundreds of features. Feature count rewarded stream density, not water presence.

Area-equivalent is proportional to actual water access:
- Large lake intersecting 2km buffer → millions of m²
- Wide river (Aare, Rhine) crossing the buffer → hundreds of thousands of m²
- Long but narrow mountain stream (class 1–2) → minimal m² regardless of length
- Small pond → near-zero m²

Scoring: min-max normalised across 184 places.

### Heritage character (10%)

ISOS national inventory (1,255 settlements) within 2km (EPSG:2056 buffer).

| Category | Score |
|---|---|
| Stadt / Kleinstadt / Flecken | 1.0 |
| Dorf / village / villaggio / Verstädtertes Dorf | 0.7 |
| Spezialfall / Sonderfall / cas particulier / Agglomeration | 0.4 |
| Unrecognised category | 0.5 |
| No ISOS within 2km | 0.0 |

Multiple ISOS within 2km: take highest score.

Note: ISOS coordinates are LV95 — use `set_crs(2056)`, not `to_crs(2056)`.

### Climate (10%)

MeteoSwiss Jun–Aug temperature, sunshine, precipitation normals. Moderate differentiator. Ticino and Valais benefit.

---

## Access layer — 40% (unchanged from v3)

| Sub-score | Weight | Data source | Method |
|---|---|---|---|
| Scenic transport | **30%** | TLM_UEBRIGE_BAHN + TLM_SCHIFFFAHRT | 14km radius (EPSG:2056) |
| Destination pull | **30%** | BFS overnights of reachable communes | SBB API reachable set |
| Cultural POIs | **25%** | OSM named museums | 14km radius (EPSG:2056) |
| Major hiking regions | **15%** | TLM WANDERWEGE trails | 20km radius |

Reachable commune set: `data_processed/sbbapi/sbbAPI_reachability.json`. Regenerate annually after December SBB timetable update.

Scenic transport includes: Gondelbahn (2), Luftseilbahn (1), Standseilbahn (0), Zahnradbahn (5), Kabinenbahn (7), all boats (0.5× weight). Boats deduplicated by NAME. `AUSSER_BETRIEB = 1` = active (note: inverted encoding — 1 = active, 2 = out of service).

Cultural POIs: named OSM museums, cap 20.

---

## Score calculation (unchanged from v3)

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

All sub-scores 0–1 before weighting. Missing values → median of 184 places. No places dropped.

---

## Changes from v3 to v4

| Item | v3 | v4 |
|---|---|---|
| Water metric | Raw TLM feature count (feature intersections) | `water_equiv_2km_m2` — lake area + river length × BREITENKLASSE width |
| River width assumption | None (feature count only) | Per-segment BREITENKLASSE attribute, fallback 3.0 m |
| `exclude.json` location | `metadata/exclude.json` (documented) | `scripts/pipeline/exclude.json` (correct) |
| Water spot-check | Lakeside towns only | Extended: bern, basel, thun added for river validation |

All other weights, thresholds, and data sources unchanged from v3.
