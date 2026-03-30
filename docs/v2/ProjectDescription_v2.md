# SmartTourismIndex — Project Description v2

> **Version note:** This is v2. The v1 document remains at `docs/v1/ProjectDescription.md`. v2 reflects the refined scoring architecture, validated data sources, and sharpened conceptual framing established in Q1 2026.

---

## Core question

**Not:** where should I go?
**But:** where should I stay — to see as much as possible, with as little friction as possible, while avoiding the crowds?

SmartTourismIndex evaluates 193 Swiss locations not as destinations in themselves but as **base camps for exploration**. The central measure is what a place *enables*, not how prominent it is.

---

## The two-layer logic

The index is built on two distinct questions that require different data and different reasoning.

### Layer 1 — Base quality (60%)

Is this a good place to spend the nights and evenings of a trip?

A good base does not need to be spectacular. It needs to be:
- **Walkable** — streets and paths you can explore on foot without a car
- **Unhurried** — not overwhelmed by tourism pressure
- **Locally rooted** — character, some history, sense of place
- **Near water** — a lake view or riverside adds quality to evenings
- **Trail access from the doorstep** — morning walks starting without transport
- **Liveable climate in summer**

This is explicitly not about being a *destination*. Lucerne is a beautiful destination. But staying in Lucerne means high prices, crowds, and noise. Staying in Sursee — 20 minutes away by train — means a quiet, walkable Swiss town on a lake, from which Lucerne is a day trip, not your hotel.

### Layer 2 — Access value (40%)

What significant day trips are possible within 1 hour by public transport?

Significant means: a gondola to the Alps, a lake boat trip, a major museum, a famous valley, a historic town. Not a local swimming pool.

The 1-hour PT envelope is calculated from actual GTFS schedule data — not straight-line distance. This is critical in Switzerland, where a mountain can make a 10km distance into a 90-minute journey or a 3-minute cable car ride.

**PT is the engine, not a score.** Strong public transport automatically expands the reachable set. Scoring it separately would be double-counting.

---

## Anti-overtourism as a scored dimension

Overtourism is the index's defining concern and its USP. It is not a filter or a disclaimer — it is built into the score as the **strongest single sub-score in the model (25% of Base)**.

The metric is **tourism intensity**: annual hotel overnights ÷ resident population. This is the EU Commission's standard indicator, used in Swiss media and research under the term *Tourismusintensität*.

| Place | Residents | Annual overnights | Tourism intensity |
|---|---|---|---|
| Zermatt | 6,099 | 1,640,200 | **269** |
| Lauterbrunnen | 2,331 | 500,405 | **215** |
| Grindelwald | 3,930 | 826,466 | **210** |
| Leukerbad | 1,426 | 205,990 | **144** |
| Zurich | ~440,000 | ~4,000,000 | **~9** |
| Venice | ~250,000 | ~11,700,000 | **~47** |

Switzerland has some of the highest tourism intensity values in the world — comparable only to Greek islands. 13 Swiss communes exceed 100 overnights per resident. The index inverts this: high intensity = high penalty. A place with intensity 5 scores near-maximum on this dimension. A place with intensity 269 scores near-zero.

**A note on the top of the ranking:** The first 50 places in the index will reasonably have high OT advantage scores. This is by design — the index is not a list of "least visited" places, but of places with strong quality and manageable pressure. A place in the top 50 is expected to have low-to-moderate tourism intensity. This is not a distortion — it is the thesis of the index.

---

## Seasonality as context, not score

Every place has a seasonal profile: how do overnights distribute across the 12 months of the year?

Leukerbad (thermal baths) is near-flat — busy year-round. Lauterbrunnen (summer valley hiking) spikes dramatically in July–August and is nearly empty in November. Zermatt has two distinct peaks — February ski season and August hiking season.

The index shows this as a **detail widget** on each place page — 12 indexed bars showing monthly relative busyness, with a volatility label (Year-round / Mildly seasonal / Strongly seasonal / Highly seasonal). This is genuinely useful information for a tourist deciding when to visit.

It is *not* scored. A highly seasonal place is not worse — it may be spectacular during its season. The index does not penalise seasonality; it informs the traveller.

---

## What the data is and is not

The index is built entirely from public Swiss federal and open data:

- **Swiss Federal Statistical Office (BFS)** — hotel overnights, bed nights, supply data
- **BFS STATPOP** — resident population per commune
- **MeteoSwiss** — summer climate normals
- **Swiss GTFS** — national PT schedule, station locations
- **swissTLM3D** (swisstopo) — national topographic model: trails, footpaths, cable cars, gondolas, boat lines, lakes, rivers
- **OSM / Geofabrik** — museums, restaurants (POI points)
- **ISOS / BAK** — federal inventory of nationally significant Swiss townscapes (1,255 settlements)

**What it is not:**
- Editorial: no human curation of which places are "nice"
- Survey-based: no visitor satisfaction scores
- Commercial: no sponsored placements, no tourism board affiliation
- Social: no TripAdvisor ratings, no Instagram metrics

The index does not claim to be complete. Hotel overnights miss Airbnb, camping, and private stays (~17 million additional nights nationally). OSM has gaps. GTFS reflects the timetable, not actual travel behaviour. These limitations are acknowledged — but the data is the best public proxy available at commune level for all 193 places.

---

## The ISOS decision — why not UNESCO

The v1 model used UNESCO World Heritage Sites as a heritage signal. This was the most obvious available data but deeply flawed for the scoring model:

- Only 6–8 Swiss communes have a UNESCO site in proximity
- Binary: UNESCO = full points, everything else = zero
- Creates a cliff effect that distorts the ranking for those few communes (notably Bellinzona)

v2 uses the **ISOS national inventory** instead — the federal government's own assessment of the 1,255 most valuable Swiss townscapes at national significance level. Stein am Rhein, Murten, Gruyères, Werdenberg, Rapperswil, Schaffhausen — all receive appropriate heritage credit without the UNESCO binary distortion. Bellinzona still scores well (it has Kleinstadt/Flecken status in ISOS) but is no longer artificially boosted above comparable heritage towns.

---

## The reachability model

The Access layer depends on computing, for each of the 193 base places, which other Swiss communes can be reached within 60 minutes by public transport.

This is calculated using actual GTFS departure data — not straight-line distance, not a "speed proxy". The algorithm:

1. Takes the anchor PT stop for each base place (nearest station)
2. Loads Tuesday 08:00–10:00 departures from the Swiss national timetable
3. Runs a forward reachability search: all stops reachable within 60 minutes total elapsed time, including transfers (minimum 3 minutes)
4. Maps reachable stops to pipeline communes within 2km

The result is a realistic set of places a tourist can actually visit in a day trip. Lauterbrunnen reaches Interlaken in 20 minutes, Bern in 55 minutes, but cannot reach Zurich. Spiez reaches Bern in 30 minutes and the Bernese Oberland in 15. Olten reaches Basel, Bern, Zurich, and Lucerne — all within 45 minutes.

This reachable commune set is the filter through which all four Access sub-scores operate.

---

## The target user

The index is primarily useful for:

**Independent travellers** who plan their own itineraries, use public transport, and want to avoid the most saturated places while still having great access to Swiss highlights.

**Multi-day trip planners** who choose a single base and do day trips — the classic Swiss "hub and spoke" travel model.

**Travellers returning to Switzerland** who have already seen the main tourist circuit and are looking for alternatives with equivalent or better access.

The index is less useful for:
- Day visitors with a single destination
- Travellers who prefer driving (PT access not relevant)
- Beach/resort holidays (Switzerland is mostly mountain/lake)

---

## Structural limitations and intellectual honesty

**Hotel overnights only.** BFS tourism data covers registered hotels and spa establishments. Airbnb, camping, hostels, private accommodation, and holiday apartments (~30% of total Swiss overnight stays nationally) are not included at commune level. Places popular for non-hotel tourism may be underestimated.

**186 of 193 communes have BFS data.** Seven places in the dataset are below the BFS data disclosure threshold (fewer than 3 regularly open hotels). Their OT score is treated as neutral — they may actually have very low tourism pressure, which would make them underrated.

**GTFS represents schedules, not crowding.** A place may be technically "reachable in 58 minutes" but require a connection that runs once per hour. The model captures reachability, not comfort or reliability of the journey.

**OSM quality is high but not perfect.** Rural areas may have fewer mapped restaurants and museums. Urban areas are comprehensively mapped. This creates a mild urban bias in the cultural POI and restaurant signals.

**ISOS quality grades are partial.** The ISOS II revision with full vector data is ongoing. Only settlements already revised have detailed zone-level quality data. The model uses the category field (`siedlungskategorie`) which is available for all 1,255 settlements.

---

## What makes the index different

Most Swiss travel recommendations are driven by:
- Historical reputation and media coverage
- Social media amplification
- Booking platform algorithms (optimised for revenue, not distribution)
- Tourism board promotion (optimised for member destinations)

SmartTourismIndex is driven by:
- Measured access potential (what can you reach?)
- Measured quality proxies (what is the place like?)
- Measured pressure (how many other tourists are already there?)

The result is a ranking that is sometimes counterintuitive. A small town in Aargau may outrank Lucerne because it has comparable access, a pleasant historic center, and almost no tourism pressure. This is not an error. It is the point.

---

## Platform principles

- **Data-driven, not editorial.** No human decides which places are included or how they score. The data decides.
- **Transparent.** Every signal has a named public data source. Methodology is fully documented.
- **Independent.** No affiliation with any tourism board, hotel group, or destination marketing organisation.
- **Cold but true.** The index does not romanticise. A village with 300 metres of footpaths, a lake 400m away, and 5 overnights per resident per year is a great base. The numbers say so.
