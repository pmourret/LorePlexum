"""Réglages de déploiement — fixés au démarrage, jamais modifiables depuis l'UI.

Distinction importante, et c'est tout l'objet de ce module :

  - Les réglages **de déploiement** (emplacement des bases SQLite, emplacement du
    fichier de configuration éditable) sont décidés par l'opérateur au lancement du
    conteneur. Ils ne changent pas en cours de vie du process : on les met en cache.

  - Les réglages **applicatifs** (chemins du JSON de contexte, des exports XML…)
    sont éditables depuis la page Paramètres, donc susceptibles de changer à chaud.
    Ils restent gérés par `backend.core.env_loader.EnvLoader`, relu à chaque requête.

Confondre les deux est la source du bug corrigé ici : la page Paramètres écrivait
dans `<racine du projet>/.env`, c'est-à-dire **dans la couche d'image Docker**. Les
chemins saisis en production étaient donc perdus au premier `docker compose build`.
`CONFIG_ENV_PATH` permet de pointer ce fichier vers le volume persistant.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du dépôt (…/TNFCDataInjector_v2), deux niveaux au-dessus de ce fichier.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DeploymentSettings(BaseSettings):
    """Variables d'environnement lues une fois au démarrage."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # Bases SQLite. En conteneur, doivent pointer sous /data (volume persistant) —
    # `deploy/Makefile` le vérifie en pré-vol.
    database_path: str = os.path.join("data", "injections.db")
    keybinds_db_path: str = os.path.join("data", "keybinds.db")

    # Fichier de configuration applicative écrit par la page Paramètres. En dev,
    # le .env du dépôt ; en conteneur, un fichier du volume persistant.
    config_env_path: str = os.path.join(PROJECT_ROOT, ".env")

    # Origine autorisée pour le frontend en développement. Vide en production :
    # Traefik sert l'API et la SPA sur le même host, donc en same-origin, et
    # aucune configuration CORS n'est nécessaire.
    dev_cors_origin: str = ""


@lru_cache
def get_deployment_settings() -> DeploymentSettings:
    """Instance unique par process (surchargeable via `app.dependency_overrides`)."""
    return DeploymentSettings()
