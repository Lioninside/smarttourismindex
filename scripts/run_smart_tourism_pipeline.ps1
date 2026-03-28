$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Split-Path -Parent $scriptDir

Set-Location $project

$scripts = @(
    "scripts\pipeline\02_bfs_origin_split.py",
    "scripts\pipeline\03_bfs_supply_demand.py",
    "scripts\pipeline\04_bfs_merge.py",
    "scripts\pipeline\05_climate.py",
    "scripts\pipeline\05b_tourism_intensity_seasonality.py",
    "scripts\pipeline\06_gtfs_access.py",
    "scripts\pipeline\07_hiking.py",
    "scripts\pipeline\08_water.py",
    "scripts\pipeline\09_heritage.py",
    "scripts\pipeline\10_osm_pois.py",
    "scripts\pipeline\11_merge_score.py",
    "scripts\pipeline\12_export_site_data.py"
)

foreach ($script in $scripts) {
    Write-Host ""
    Write-Host "Running $script ..."
    python $script
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Stopped at $script because of an error." -ForegroundColor Red
        break
    }
}
