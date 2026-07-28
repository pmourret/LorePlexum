"""Providers `Depends` — remplacent les singletons de module de l'ancien webapp.

Avant, `webapp/main.py` créait `db` et `keys_db` à l'import et reconstruisait la
configuration à chaque appel via un `build_service()` global. Rien n'était
surchargeable, donc rien n'était testable sans toucher au vrai `.env` ni aux vraies
bases. Ici, tout passe par des dépendances FastAPI, que les tests remplacent avec
`app.dependency_overrides`.

Cycle de vie, et il n'est pas uniforme :

  - **Bases de données** : une instance par process (`lru_cache`). Le schéma n'est
    initialisé qu'une fois, et c'est sûr en multi-thread parce que `InjectionDatabase`
    et `KeyBindDatabase` ouvrent une connexion `sqlite3` par opération — l'objet mis
    en cache ne porte aucune connexion partagée.
  - **Reporter et service** : une instance par requête. Le reporter accumule le
    journal d'exécution d'une injection, et les chemins du service peuvent changer
    à chaud depuis la page Paramètres — les mettre en cache figerait les deux.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from backend.app.config import DeploymentSettings, get_deployment_settings
from backend.app.env_file import validate_settings
from backend.core.database import InjectionDatabase
from backend.core.env_loader import EnvLoader
from backend.core.injection_service import InjectionService
from backend.core.keybinds import KeyBindDatabase
from backend.core.reporter import Reporter


class ConfigurationError(RuntimeError):
    """Configuration applicative absente ou invalide (chemins introuvables).

    Traduite en `503 Service Unavailable` par le gestionnaire d'exceptions de
    `backend.app.main` : le service est correct, c'est son environnement qui ne
    l'est pas, et l'utilisateur doit passer par la page Paramètres.
    """


Settings = Annotated[DeploymentSettings, Depends(get_deployment_settings)]


@lru_cache
def _injection_db(database_path: str) -> InjectionDatabase:
    return InjectionDatabase(database_path)


@lru_cache
def _keybind_db(keybinds_db_path: str) -> KeyBindDatabase:
    return KeyBindDatabase(keybinds_db_path)


def get_db(settings: Settings) -> InjectionDatabase:
    """Base d'archivage des injections (historique + anti-doublon)."""
    return _injection_db(settings.database_path)


def get_keys_db(settings: Settings) -> KeyBindDatabase:
    """Base de la carte des touches, indépendante de l'archivage narratif."""
    return _keybind_db(settings.keybinds_db_path)


def get_reporter() -> Reporter:
    """Journal d'exécution neuf pour chaque requête."""
    return Reporter()


def get_config_status(settings: Settings) -> tuple:
    """(ok, checks) de la configuration applicative courante."""
    return validate_settings(settings.config_env_path)


def get_service(
    settings: Settings,
    db: Annotated[InjectionDatabase, Depends(get_db)],
    reporter: Annotated[Reporter, Depends(get_reporter)],
) -> InjectionService:
    """Service d'injection configuré, ou `ConfigurationError` si l'env est invalide.

    `EnvLoader` est reconstruit à chaque requête — c'est voulu : la page Paramètres
    peut modifier les chemins en cours de vie du process.
    """
    ok, checks = validate_settings(settings.config_env_path)
    if not ok:
        problems = [f"{c['label']} ({c['key']}) : {c['message']}"
                    for c in checks if c["status"] == "error"]
        raise ConfigurationError(
            "Configuration incomplète ou invalide — " + " ; ".join(problems)
        )

    # Le MÊME fichier que celui que `validate_settings` vient de juger : sans quoi
    # la validation et le chargement portent sur deux sources différentes.
    try:
        env = EnvLoader(settings.config_env_path)
    except ValueError as exc:
        raise ConfigurationError(str(exc)) from exc

    return InjectionService(
        env.get_paths(),
        pdf_export_file=env.pdf_export_file,
        reporter=reporter,
        db=db,
    )


Db = Annotated[InjectionDatabase, Depends(get_db)]
KeysDb = Annotated[KeyBindDatabase, Depends(get_keys_db)]
Service = Annotated[InjectionService, Depends(get_service)]
ReporterDep = Annotated[Reporter, Depends(get_reporter)]
ConfigStatus = Annotated[tuple, Depends(get_config_status)]
