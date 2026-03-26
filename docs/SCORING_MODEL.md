# Scoring Model

This document describes the current SmartTourismIndex ranking model.

## Top-level weights
- Base quality — 25%
- Access value — 35%
- Practical comfort — 20%
- Anti-overtourism advantage — 20%

## Base quality
How good is the place itself as a base?

Includes:
- heritage / old-town quality
- walkable center
- local culture presence
- local restaurant presence
- local water setting

## Access value
What can be unlocked within roughly 1 hour by public transport?

Includes:
- scenic transport access
- nature access
- water access
- cultural access
- diversity bonus

Scenic transport is intentionally weighted highly inside Access value and includes:
- mountain railways
- cable cars
- gondolas
- funiculars
- scenic trains
- boat trips

## Practical comfort
How easy and pleasant is the stay without a car?

Includes:
- PT strength
- climate comfort
- accommodation readiness

## Anti-overtourism advantage
How much does the place avoid the downsides of obvious hotspots while still being strong?

Includes:
- hiddenness advantage
- tourism pressure proxy
- overtourism penalty

## Current implementation note
The current code in `11_merge_score.py` is an MVP implementation.
Main future improvements:
- better normalization
- clearer missing-data logic
- better scenic transport feature engineering
- deeper heritage / old-town integration
- better hiddenness math
