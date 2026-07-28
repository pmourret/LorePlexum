"""Schémas partagés par plusieurs routers."""

from typing import Literal

from pydantic import BaseModel, Field


class LogMessage(BaseModel):
    """Une entrée du journal d'exécution produit par `Reporter`."""

    level: Literal["info", "success", "error", "warning"]
    message: str
    timestamp: str


class Category(BaseModel):
    """Catégorie d'injection et le fichier XML TakeNotes qu'elle vise."""

    key: str = Field(description="Clé technique, ex. « journal »")
    xml_file: str = Field(description="Fichier d'export TakeNotes correspondant")


class ConfigStatusOut(BaseModel):
    """État de santé de l'application et de sa configuration."""

    status: Literal["ok", "unconfigured"]
    config_ok: bool
    problems: list[str] = []
