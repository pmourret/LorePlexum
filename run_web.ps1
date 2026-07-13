# Lance l'interface web TNFCDataInjector (FastAPI + HTMX).
# Active le venv puis démarre le serveur Uvicorn, et ouvre le navigateur.
Set-Location -Path $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"
Start-Process "http://127.0.0.1:8000/"
python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
