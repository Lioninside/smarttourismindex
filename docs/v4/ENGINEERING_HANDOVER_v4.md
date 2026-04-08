# SmartTourismIndex — Engineering Handover v4

> **Version history:** v1 → initial build. v2 → 2-layer scoring rewrite. v3 → SBB API reachability, 14km spatial radius, 184 places. v4 → water scoring overhaul, website frontend complete.
> Previous versions archived at `docs/v2/` (v2) and `docs/v2/v3/` (v3).

---

## What changed in v4

### Water scoring: feature count replaced by area-equivalent metric

The most significant scoring change in v4. The old approach counted raw TLM feature intersections within a 2km buffer — this systematically underrated lakeside towns because a large lake (Lake Thun, Lake Lucerne) is a single polygon, while alpine stream-heavy areas generate hundreds of short river line segments.

**New metric: `water_equiv_2km_m2`** written to `data_processed/water/water_metrics.json`

```
water_equiv_2km_m2 = Σ clipped lake polygon area (m²)
                   + Σ (clipped river length (m) × BREITENKLASSE_width)
```

River width from TLM `BREITENKLASSE` attribute per segment:

| Class | Width range | Width used |
|---|---|---|
| 1 | < 1 m | 0.5 m |
| 2 | 1–5 m | 3.0 m |
| 3 | 5–15 m | 10.0 m |
| 4 | 15–50 m | 30.0 m |
| 5 | > 50 m | 75.0 m |
| missing | — | 3.0 m (fallback) |

Effect:
- Spiez (Lake Thun within 2km): score reflects actual lake presence, not feature count of 91
- Bern (Aare, BREITENKLASSE 4–5): wide river contributes proportional equivalent area
- Basel (Rhine, BREITENKLASSE 5): major river correctly weighted
- Long but narrow alpine streams (class 1–2): contribute near-zero even if lengthy

`08_water.py` now computes and writes `water_equiv_2km_m2` and `water_equiv_10km_m2`. The old `water_features_2km` and `water_features_10km` (raw counts) remain in output for diagnostics but are no longer used for scoring.

`11_merge_score.py` reads `water_equiv_2km_m2` for the water sub-score (15% of Base). min-max normalised across 184 places.

Spot-check in `08_water.py` extended to include `bern`, `basel`, `thun` alongside existing lakeside towns.

**Requires `08_water.py` rerun before `11_merge_score.py`** on any existing installation. Old `water_metrics.json` files lack `water_equiv_2km_m2` and will score water as 0 with a logged warning.

### exclude.json location corrected

v3 documented `metadata/exclude.json`. Correct location is `scripts/pipeline/exclude.json`.

File was accidentally deleted during development and recreated. Contents:
```json
["monteceneri"]
```

Applied in `11_merge_score.py` before scoring and in `12_export_site_data.py` before export. If missing, Monteceneri is included in output — verify after any clean checkout.

### Website frontend: complete

All four pages written, deployed, and stable:
- `website/index.html` — ranking, hero, score explanation, about, feedback
- `website/methodology.html` — scoring explanation for non-technical readers
- `website/about.html` — project background, open-source positioning
- `website/contact.html` — LinkedIn + GitHub CTAs only, no email

Content rules in effect:
- LinkedIn (`https://www.linkedin.com/in/lioninside/`) — primary CTA
- GitHub (`https://github.com/Lioninside/smarttourismindex`) — secondary CTA
- No email addresses anywhere
- Data sources always end with "and more." (open list)

### Bar label width fix

`.bar-label` in `website/style.css` changed from `min-width: 52px` to `width: 90px; flex-shrink: 0`. "ACCESS SCORE" is wider than "BASE SCORE" at 10px uppercase — the old `min-width` caused different bar track widths, making the bars visually incomparable. Fixed: both bars now share the same track width.

### Expanded card redesign

Collapsed card shows: BASE SCORE bar, ACCESS SCORE bar (numeric scores 0–100).

Expanded card grid:
- Listed Townscape (ISOS): YES / NO
- Tourism Pressure: LOW / MODERATE / HIGH / VERY HIGH
- Destinations (≤1.5h): up to 3 from SWISS_TOP20 curated list
- Seasonal Pattern: SVG line chart (single blue line, JFMAMJJASOND labels)

Tourism Pressure derived from `scores.sub.anti_overtourism` (0–100, inverted):

| Value | Label |
|---|---|
| > 75 | LOW |
| > 50 | MODERATE |
| > 25 | HIGH |
| ≤ 25 | VERY HIGH |

Note: high `anti_overtourism` = low actual pressure. Locarno shows LOW pressure despite 314K annual overnights because its tourism intensity (overnights ÷ residents) is ~21 — low relative to alpine resorts (Zermatt ~270, Lauterbrunnen ~215).

### SWISS_TOP20 curated list (app.js)

31-place list in priority order controls which places can appear as "Nearby highlights" in expanded cards. Only places in this list AND in `detail.reachable_slugs` are shown (max 3, priority order):

```javascript
const SWISS_TOP20 = [
  "zurich", "geneve", "zermatt", "basel", "luzern",
  "bern", "lausanne", "interlaken", "davos", "st-moritz",
  "grindelwald", "lugano", "lauterbrunnen", "montreux", "ascona",
  "arosa", "pontresina", "vernier", "saanen", "engelberg",
  "locarno", "st-gallen", "laax", "saas-fee", "chur",
  "vaz-obervaz", "winterthur", "leukerbad", "adelboden", "crans-montana",
  "flims"
];
```

Note: `vaz-obervaz` is known publicly as Lenzerheide.

### PowerShell runner fix

`Get-Date - $t` fails in PowerShell (minus parsed as parameter name). Fixed to `((Get-Date) - $t).TotalSeconds` in both `run_smart_tourism_pipeline.ps1` and `run_smart_tourism_pipeline_skip.ps1`.

---

## Engineering issues new in v4

### `water_equiv_2km_m2` requires pipeline rerun

Any existing `water_metrics.json` without this field must be regenerated. `11_merge_score.py` logs a warning and uses 0 if the field is absent — the water sub-score will be incorrect until `08_water.py` is rerun.

### `BREITENKLASSE` fallback for missing segments

If a TLM river segment has no `BREITENKLASSE` attribute, `_river_equiv_area()` applies `RIVER_WIDTH_FALLBACK_M = 3.0`. This is conservative. The fallback is defined as a constant at the top of `08_water.py` and can be adjusted.

### Tourism Pressure label requires new score format

The expanded card Tourism Pressure label reads `scores.sub.anti_overtourism`. This field is only present in `place_scores.json` generated by the current `11_merge_score.py`. Old pipeline output (pre-v3) used `subscores.anti_overtourism` which is popped at export by `12_export_site_data.py`. Always run the full pipeline after updating scripts.

---

## Sanity checks after full pipeline run (v4)

- 184 places in `data_export/places-index.json`
- `monteceneri` absent from output
- `water_metrics.json` entries have `water_equiv_2km_m2` field
- Spiez `water_equiv_2km_m2` substantially higher than feature count of 91 suggested
- Bern, Basel: meaningful water score from Aare / Rhine
- Small alpine stream-heavy places: water score not dominating rank
- Locarno Tourism Pressure: LOW — correct (low per-capita intensity)
- Expanded card bar tracks visually equal width for BASE SCORE and ACCESS SCORE

---

## No changes to scoring weights in v4

The scoring architecture (Base 60% / Access 40%, all sub-score weights) is unchanged from v3. Only the water metric input changed. Scores will shift for water-adjacent places after rerun.
