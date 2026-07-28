# Lance LorePlexum en developpement : backend FastAPI + frontend Vite.
#
# Deux serveurs, comme en production. Le proxy Vite renvoie /api vers le backend,
# donc le navigateur reste en same-origin et il n'y a aucun CORS a configurer.
#
#   .\run_dev.ps1            # les deux serveurs
#   .\run_dev.ps1 -Backend   # backend seul (utile pour /api/docs)
param(
    [switch]$Backend,
    [switch]$Frontend
)

Set-Location -Path $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

$runBackend  = $Backend -or -not $Frontend
$runFrontend = $Frontend -or -not $Backend

if ($runBackend -and $runFrontend) {
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "Set-Location '$PSScriptRoot'; & '.\.venv\Scripts\Activate.ps1'; python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000"
    )
    Start-Sleep -Seconds 2
    Start-Process 'http://localhost:5173/'
    Set-Location "$PSScriptRoot\frontend"
    npm run dev
}
elseif ($runBackend) {
    Start-Process 'http://127.0.0.1:8000/api/docs'
    python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
}
else {
    Set-Location "$PSScriptRoot\frontend"
    npm run dev
}
