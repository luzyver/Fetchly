$ErrorActionPreference = "Stop"

docker compose config --quiet
docker compose up --build -d --wait
docker compose exec web python manage.py check
docker compose exec web python manage.py check_capabilities

$port = if ($env:FETCHLY_PORT) { $env:FETCHLY_PORT } else { "5050" }
$live = Invoke-RestMethod "http://127.0.0.1:$port/health/live"
$ready = Invoke-RestMethod "http://127.0.0.1:$port/health/ready"
if (-not ($live.ok -and $ready.ok)) { throw "Fetchly belum sehat" }

Write-Host "Fetchly smoke check passed."
