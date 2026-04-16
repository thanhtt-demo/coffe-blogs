# Start both API server and Astro dev server
# Usage: .\dev.ps1

Write-Host "Starting Ba Te dev environment..." -ForegroundColor Cyan

# Start API server as a job
Write-Host "Starting API server on :8000..." -ForegroundColor Yellow
$apiJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\pipeline
    python -m uvicorn coffee_pipeline.api.app:app --reload --port 8000
}

Start-Sleep -Seconds 2

# Start Astro dev server as a job
Write-Host "Starting Astro dev server on :4321..." -ForegroundColor Yellow
$astroJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    npm run dev
}

Write-Host ""
Write-Host "Both servers running:" -ForegroundColor Green
Write-Host "  API:   http://localhost:8000"
Write-Host "  Web:   http://localhost:4321"
Write-Host "  Admin: http://localhost:4321/admin"
Write-Host ""
Write-Host "Press Enter to stop both servers." -ForegroundColor Gray

# Stream output from both jobs until user presses Enter
while (-not [Console]::KeyAvailable) {
    Receive-Job $apiJob -ErrorAction SilentlyContinue
    Receive-Job $astroJob -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}
$null = [Console]::ReadKey($true)

# Cleanup
Write-Host "`nStopping servers..." -ForegroundColor Red
Stop-Job $apiJob, $astroJob -ErrorAction SilentlyContinue
Remove-Job $apiJob, $astroJob -Force -ErrorAction SilentlyContinue

# Kill anything still on those ports
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort 4321 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host "Stopped." -ForegroundColor Red
