"""Lecture et écriture de la configuration applicative."""

from fastapi import APIRouter

from backend.app import env_file
from backend.app.deps import Settings
from backend.app.schemas.settings import SettingCheck, SettingsOut, SettingsWrite

router = APIRouter(tags=["settings"])


def _current(settings) -> SettingsOut:
    ok, checks = env_file.validate_settings(settings.config_env_path)
    return SettingsOut(
        all_ok=ok,
        checks=[SettingCheck(**c) for c in checks],
        config_path=settings.config_env_path,
    )


@router.get("/settings", response_model=SettingsOut,
            summary="Configuration courante et résultat de sa validation")
def get_settings(settings: Settings) -> SettingsOut:
    """Renvoie la configuration **effective**.

    C'est-à-dire les variables d'environnement (injectées par `env_file:` en
    conteneur) complétées par le fichier éditable — l'ordre de priorité que
    `EnvLoader` applique réellement.
    """
    return _current(settings)


@router.put("/settings", response_model=SettingsOut,
            summary="Écrit la configuration et renvoie sa validation")
def update_settings(payload: SettingsWrite, settings: Settings) -> SettingsOut:
    """Écrit dans le fichier désigné par `CONFIG_ENV_PATH`.

    Seules les clés déclarées dans `env_file.FIELDS` sont écrites : une requête ne
    peut pas injecter une variable arbitraire dans la configuration.
    """
    known = {k: v for k, v in payload.values.items() if k in env_file.FIELD_KEYS}
    env_file.save_settings(settings.config_env_path, known)
    return _current(settings)
