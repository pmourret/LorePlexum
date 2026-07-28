"""Fixtures partagées : un environnement applicatif complet et jetable.

Les tests écrits avant ce refactor utilisent `unittest.TestCase` ; les nouveaux
utilisent les fixtures pytest, nettement plus lisibles pour monter une application
FastAPI avec ses dépendances surchargées. Les deux styles coexistent sous le même
lanceur (`python -m pytest`).

Chaque test reçoit son propre dossier temporaire : copies des exports XML de
`samples/`, JSON de contexte neuf, bases SQLite vierges. Rien n'est partagé entre
tests, et surtout rien ne touche aux vraies données du projet.
"""

import json
import os
import shutil

import pytest
from fastapi.testclient import TestClient

from backend.app.config import DeploymentSettings, get_deployment_settings
from backend.app.main import create_app
from backend.core.database import InjectionDatabase
from backend.core.injection_service import InjectionService
from backend.core.keybinds import KeyBindDatabase
from backend.core.reporter import Reporter

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")

# Variables d'environnement de configuration applicative, pointées sur le bac à
# sable. `EnvLoader` les relit à chaque requête.
ENV_KEYS = (
    "FULL_CONTEXT_JSON_PATH",
    "ENTRIES_DIR",
    "METADATAS_DIR",
    "TAKE_NOTES_EXPORT_DIR",
    "PDF_OUTPUT_PATH",
    "PDF_EXPORT_FILE",
    "MAX_TOKENS_PER_ENTRY",
)

EMPTY_CONTEXT = {"character_arc": {}}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Arborescence applicative complète et isolée.

    Retourne un dict de chemins ; positionne aussi les variables d'environnement
    correspondantes, puisque c'est ainsi que la configuration arrive réellement en
    production (`env_file:` du docker-compose).
    """
    export_dir = tmp_path / "exports"
    entries_dir = tmp_path / "entries"
    metadatas_dir = tmp_path / "metadatas"
    pdf_dir = tmp_path / "pdf"
    for directory in (export_dir, entries_dir, metadatas_dir, pdf_dir):
        directory.mkdir()

    for name in os.listdir(SAMPLES_DIR):
        if name.endswith(".xml"):
            shutil.copy2(os.path.join(SAMPLES_DIR, name), export_dir / name)

    context_path = tmp_path / "full_context.json"
    context_path.write_text(json.dumps(EMPTY_CONTEXT), encoding="utf-8")

    config_env_path = tmp_path / "app.env"
    config_env_path.write_text("", encoding="utf-8")

    values = {
        "FULL_CONTEXT_JSON_PATH": str(context_path),
        "ENTRIES_DIR": str(entries_dir),
        "METADATAS_DIR": str(metadatas_dir),
        "TAKE_NOTES_EXPORT_DIR": str(export_dir),
        "PDF_OUTPUT_PATH": str(pdf_dir),
        "PDF_EXPORT_FILE": "TEST",
        "MAX_TOKENS_PER_ENTRY": "500",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    return {
        "root": tmp_path,
        "context_path": context_path,
        "export_dir": export_dir,
        "entries_dir": entries_dir,
        "metadatas_dir": metadatas_dir,
        "pdf_dir": pdf_dir,
        "config_env_path": config_env_path,
        "database_path": tmp_path / "injections.db",
        "keybinds_db_path": tmp_path / "keybinds.db",
        "values": values,
    }


@pytest.fixture
def settings(sandbox) -> DeploymentSettings:
    return DeploymentSettings(
        database_path=str(sandbox["database_path"]),
        keybinds_db_path=str(sandbox["keybinds_db_path"]),
        config_env_path=str(sandbox["config_env_path"]),
        dev_cors_origin="",
    )


@pytest.fixture
def db(sandbox) -> InjectionDatabase:
    return InjectionDatabase(str(sandbox["database_path"]))


@pytest.fixture
def keys_db(sandbox) -> KeyBindDatabase:
    return KeyBindDatabase(str(sandbox["keybinds_db_path"]))


@pytest.fixture
def reporter() -> Reporter:
    return Reporter()


@pytest.fixture
def service(sandbox, db, reporter) -> InjectionService:
    """Service branché sur le bac à sable, PDF désactivé par défaut côté appelant."""
    return InjectionService(
        paths={
            "full_context_json_path": str(sandbox["context_path"]),
            "entries_dir": str(sandbox["entries_dir"]),
            "metadatas_dir": str(sandbox["metadatas_dir"]),
            "take_notes_export_dir": str(sandbox["export_dir"]),
        },
        pdf_export_file="TEST",
        reporter=reporter,
        db=db,
    )


@pytest.fixture
def client(settings) -> TestClient:
    """Application API seule (sans l'UI HTMX), dépendances pointées sur le bac à sable."""
    app = create_app(legacy_ui=False)
    app.dependency_overrides[get_deployment_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def unconfigured_client(tmp_path, monkeypatch) -> TestClient:
    """Application dont la configuration applicative est absente.

    Sert à vérifier que l'API répond `503` (et non `500`) et que `/health` reste
    joignable — c'est ce qui permet au frontend de rediriger vers les Paramètres.
    """
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    empty_env = tmp_path / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    settings = DeploymentSettings(
        database_path=str(tmp_path / "injections.db"),
        keybinds_db_path=str(tmp_path / "keybinds.db"),
        config_env_path=str(empty_env),
        dev_cors_origin="",
    )

    app = create_app(legacy_ui=False)
    app.dependency_overrides[get_deployment_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
