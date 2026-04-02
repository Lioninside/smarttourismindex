Base to Place (GTFS 1h reachability) — risks confirmed:

Wrong hub — if main_station_name in places_master.csv points to a small halt instead of the main interchange, the reachability graph starts from the wrong node. Splügen's station matters enormously here.
100km pre-filter coordinate error — the GTFS algorithm likely excludes stops >100km away before doing time-based calculation. A coordinate error puts the wrong stops in/out of that pre-filter.
BFS commune edge cases — places on commune borders or with split settlements may map to the wrong anchor.
Outdated station_id — if station_id in the CSV doesn't match the current GTFS stop_id, the anchor stop lookup fails and falls back to nearest-by-coordinates which may be wrong.
Score = number × importance — destination pull uses BFS overnights (importance proxy), not raw count. Correct.

This approach handles mountains correctly — it uses real timetable travel times, so a mountain that makes a journey 2h33min simply means that place isn't reachable within 1h. Geography is implicit in the schedules.

Base to Access (14km radius) — risks confirmed:

Mountain between — the 14km is straight-line geographic distance. It has no knowledge of mountains, passes, or actual travel time. Splügen–Vals is the perfect example: ~12km straight line, mountain in between, 2h33min actual journey. The gondola at Vals would incorrectly count for Splügen's mountain access score.
Score = transport line count + boat count — confirmed.

This approach does NOT handle mountains — it's a circle, not a reachability model.