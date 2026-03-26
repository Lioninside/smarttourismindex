$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptsDir = Split-Path -Parent $scriptDir
$project = Split-Path -Parent $scriptsDir

$data = "C:\Users\stc-cbartlome\Downloads\AllData"

$folders = @(
    "$project\data_raw\bfs",
    "$project\data_raw\climate",
    "$project\data_raw\gtfs",
    "$project\data_raw\swisstopo",
    "$project\data_raw\heritage",
    "$project\data_raw\osm",
    "$project\data_processed\bfs",
    "$project\data_processed\climate",
    "$project\data_processed\gtfs",
    "$project\data_processed\hiking",
    "$project\data_processed\water",
    "$project\data_processed\heritage",
    "$project\data_processed\osm",
    "$project\data_processed\final",
    "$project\data_export",
    "$project\data_export\places"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
}

Write-Host "Setup finished."