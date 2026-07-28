# Lance le backend LorePlexum (API /api/v1 + interface HTMX en sursis).
# Active le venv puis démarre le serveur Uvicorn, et ouvre le navigateur.
Set-Location -Path $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"
Start-Process "http://127.0.0.1:8000/"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
