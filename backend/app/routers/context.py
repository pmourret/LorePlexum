"""Données de contexte alimentant les formulaires : santé, catégories, arcs, calendrier."""

from fastapi import APIRouter, HTTPException, Query

from backend.app.deps import ConfigStatus, Service
from backend.app.schemas.calendar import (
    CalendarOut,
    GameDate,
    Month,
    SuggestedDateOut,
)
from backend.app.schemas.common import Category, ConfigStatusOut
from backend.core import tamrielic_calendar as calendar
from backend.core.files import FileChooser
from backend.core.injection_service import XML_FILES_MAPPING

router = APIRouter(tags=["context"])


@router.get("/health", response_model=ConfigStatusOut, summary="Santé et configuration")
def health(config: ConfigStatus) -> ConfigStatusOut:
    """Ne dépend pas de `get_service` : doit répondre **même** si la config est cassée."""
    ok, checks = config
    return ConfigStatusOut(
        status="ok" if ok else "unconfigured",
        config_ok=ok,
        problems=[f"{c['label']} : {c['message']}"
                  for c in checks if c["status"] == "error"],
    )


@router.get("/categories", response_model=list[Category])
def list_categories() -> list[Category]:
    return [Category(key=key, xml_file=xml) for key, xml in XML_FILES_MAPPING.items()]


@router.get("/arcs", response_model=list[str],
            summary="Arcs existants dans le JSON de contexte")
def list_arcs(service: Service) -> list[str]:
    return service.list_arcs()


@router.get("/metadata-files", response_model=list[str],
            summary="Fichiers du dossier de métadonnées (vestige V1, facultatif)")
def list_metadata_files(service: Service) -> list[str]:
    metadatas_dir = service.paths.get("metadatas_dir")
    if not metadatas_dir:
        return []
    try:
        return FileChooser.list_files(metadatas_dir)
    except (FileNotFoundError, OSError):
        # Dossier absent, vide ou inaccessible : ce champ est facultatif, on ne
        # transforme pas ça en erreur d'API.
        return []


@router.get("/calendar", response_model=CalendarOut,
            summary="Calendrier tamrielien complet (données statiques)")
def get_calendar() -> CalendarOut:
    """Renvoie tout le calendrier en un appel : le client calcule localement.

    Remplace les deux allers-retours HTMX `/suggest-date` et `/date-days`.
    """
    return CalendarOut(
        eras=calendar.ERAS,
        months=[
            Month(index=i, name_en=en, name_fr=fr, days=days)
            for i, (en, fr, days) in enumerate(calendar.MONTHS)
        ],
        weekdays=calendar.WEEKDAYS,
        default=GameDate(**calendar.DEFAULT),
    )


@router.get("/calendar/suggest", response_model=SuggestedDateOut,
            summary="Date proposée par défaut pour une catégorie")
def suggest_date(service: Service, category: str = Query(...)) -> SuggestedDateOut:
    """Dernière date connue du XML de la catégorie, décomposée en composants."""
    if category not in XML_FILES_MAPPING:
        raise HTTPException(status_code=422, detail=f"Catégorie inconnue : {category}.")

    last = service.suggest_entry_date(category)
    parsed = calendar.parse_date(last)
    date = GameDate(**(parsed if parsed else calendar.DEFAULT))
    return SuggestedDateOut(
        date=date,
        source="last_known" if parsed else "default",
        stored=date.to_stored_string(),
    )
