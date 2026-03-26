$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $scriptDir

Set-Location $project

$steps = @(
    @{ script = "scripts\pipeline\02_bfs_origin_split.py"; output = "data_processed\bfs\bfs_origin_split_2025.json" },
    @{ script = "scripts\pipeline\03_bfs_supply_demand.py"; output = "data_processed\bfs\bfs_supply_demand_2025.json" },
    @{ script = "scripts\pipeline\04_bfs_merge.py"; output = "data_processed\bfs\bfs_place_metrics_2025.json" },
    @{ script = "scripts\pipeline\05_climate.py"; output = "data_processed\climate\climate_metrics_jja.json" },
    @{ script = "scripts\pipeline\06_gtfs_access.py"; output = "data_processed\gtfs\gtfs_access_metrics.json" },
    @{ script = "scripts\pipeline\07_hiking.py"; output = "data_processed\hiking\hiking_metrics.json" },
    @{ script = "scripts\pipeline\08_water.py"; output = "data_processed\water\water_metrics.json" },
    @{ script = "scripts\pipeline\09_heritage.py"; output = "data_processed\heritage\heritage_metrics.json" },
    @{ script = "scripts\pipeline\10_osm_pois.py"; output = "data_processed\osm\osm_poi_metrics.json" },
    @{ script = "scripts\pipeline\11_merge_score.py"; output = "data_processed\final\place_scores.json" },
    @{ script = "scripts\pipeline\12_export_site_data.py"; output = "data_export\places-index.json" }
)

foreach ($step in $steps) {
    $script = $step.script
    $output = $step.output

    Write-Host ""

    if (Test-Path $output) {
        Write-Host "Skipping $script (output exists: $output)" -ForegroundColor Yellow
        continue
    }

    Write-Host "Running $script ..." -ForegroundColor Cyan
    python $script

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Stopped at $script because of an error." -ForegroundColor Red
        break
    }
}