# Image du backend LorePlexum : API FastAPI + génération PDF WeasyPrint.
#
# Ne sert plus aucune page — le frontend React est un service distinct (voir
# frontend/Dockerfile). Cible : serveur Docker « hiatus », écrit sur le partage
# SMB « auditus » monté dans le conteneur (voir deploy/docker-compose.yml).
#
# Contexte de build attendu : la RACINE du dépôt, pour pouvoir copier
# `backend/` et `requirements.txt` ensemble.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Dépendances système de WeasyPrint (Pango / Cairo / gdk-pixbuf) + polices.
# Sans elles, `import weasyprint` échoue : c'est ce qui remplace l'installation
# manuelle de wkhtmltopdf de l'ancienne version.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libcairo2 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Couche de dépendances séparée pour profiter du cache tant que requirements
# ne change pas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Seul le backend entre dans l'image : ni le frontend, ni les tests, ni les
# scripts de développement.
COPY backend/ ./backend/

EXPOSE 8000

# Écoute sur 0.0.0.0 (et non 127.0.0.1) pour être joignable hors du conteneur.
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
