"""Contrat d'API de la page Paramètres."""

from typing import Literal

from pydantic import BaseModel, Field


class SettingCheck(BaseModel):
    """Un champ de configuration et le résultat de sa validation."""

    key: str
    label: str
    value: str
    required: bool
    kind: Literal["file", "dir"] | None = Field(
        default=None, description="Type de chemin vérifié ; null si non vérifié"
    )
    status: Literal["ok", "error", "empty"]
    message: str


class SettingsOut(BaseModel):
    all_ok: bool
    checks: list[SettingCheck]
    config_path: str = Field(
        description="Fichier réellement écrit par PUT (voir CONFIG_ENV_PATH)"
    )


class SettingsWrite(BaseModel):
    """Corps de `PUT /api/v1/settings` : {clé: valeur} pour les champs connus.

    Les clés inconnues sont ignorées — on n'écrit jamais une variable arbitraire
    dans le fichier de configuration depuis une requête HTTP.
    """

    values: dict[str, str]
