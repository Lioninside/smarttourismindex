# Data Sources

This document lists the current data sources used by SmartTourismIndex, what they are used for, and how they should be refreshed.

## BFS tourism tables
Files:
- `px-x-1003020000_101_*.csv`
- `px-x-1003020000_201_*.csv`

Purpose:
- arrivals
- overnight stays
- accommodation supply
- room / bed occupancy
- domestic vs international demand split
- tourism pressure / hiddenness logic

## MeteoSwiss climate normals
Purpose:
- summer temperature
- summer precipitation
- summer sunshine

Notes:
- current pipeline uses June, July, August
- NetCDF handling requires `decode_times=False`
- grid selection is done via LV95 `N` / `E`

## Swiss GTFS
Purpose:
- anchor stop / station
- PT strength proxy
- route richness
- future scenic transport logic

## swissTLM3D
Current main file:
- `swissTLM3D_2026_LV95_LN02.gdb`

Currently used for:
- water
- hiking

Future candidates:
- scenic transport
- settlement centers
- better walkability / base-quality logic

## OSM / Geofabrik GeoPackage
File:
- `osm_switzerland.gpkg`

Layer:
- `gis_osm_pois_free`

Field:
- `fclass`

Used for:
- museums
- restaurants

## UNESCO
File:
- `swiss_unesco_sites.json`

Used for:
- UNESCO enrichment
- heritage / culture boost

## ISOS
Planned as the main long-term heritage / old-town quality input.
