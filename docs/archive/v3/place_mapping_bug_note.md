# place_mapping.json — Bug Found

## Bug: Buchs (SG) has wrong canton

In `metadata/place_mapping.json`, the entry for `"Buchs (SG)"` has:
```json
"canton": "BE"
```

This should be:
```json
"canton": "SG"
```

Buchs is in St. Gallen, not Bern. Fix before next commit.

## Also note: Moutier (JU) has placeholder coordinates

```json
"lat": "...",
"lon": "..."
```

These need real coordinates for Moutier (JU). The canton transferred from BE to JU in 2023. Approximate: lat 47.279, lon 7.372.
