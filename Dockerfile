# Image de l'application web TNFCDataInjector (FastAPI + WeasyPrint).
# Cible : serveur Docker « hiatus », écrit sur le partage SMB « auditus » monté
# dans le conteneur (voir docker-compose.yml).
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

COPY . .

EXPOSE 8000

# Écoute sur 0.0.0.0 (et non 127.0.0.1) pour être joignable hors du conteneur.
CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
