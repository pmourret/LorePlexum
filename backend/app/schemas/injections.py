"""Contrat d'API du pipeline d'injection et de l'historique."""

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.calendar import GameDate
from backend.app.schemas.common import LogMessage


class InjectionCreate(BaseModel):
    """Corps de `POST /api/v1/injections`.

    Le résumé et le texte sont deux champs distincts : le découpage par balises
    `Resume :` / `Text :` appartenait au CLI, retiré lors de ce refactor.
    """

    category: str
    text: str = Field(min_length=1, description="Corps du journal enrichi (requis)")
    resume: str = ""
    metadata: dict = Field(default_factory=dict)
    arc: str | None = Field(
        default=None,
        description="Arc cible. Vide ou absent -> nouvel arc auto-numéroté.",
    )
    entry_date: GameDate | None = Field(
        default=None,
        description="Date de session. Absente -> dernière date connue de la catégorie.",
    )
    max_tokens: int | None = Field(
        default=None, gt=0, description="Largeur de segmentation XML. Absent -> env."
    )
    generate_pdf: bool = True
    allow_duplicate: bool = Field(
        default=False,
        description="Force l'injection malgré une empreinte de texte déjà connue.",
    )

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le texte principal ne peut pas être vide.")
        return value


class InjectionSummary(BaseModel):
    """Ligne d'historique — assez pour un tableau, sans le corps du texte."""

    id: int
    date_injection: str
    categorie: str | None = None
    arc: str | None = None
    entry_number: int | None = None
    date_session: str | None = None
    resume: str | None = None
    xml_file: str | None = None
    has_pdf: bool = False

    @classmethod
    def from_row(cls, row: dict) -> "InjectionSummary":
        return cls(**{k: row.get(k) for k in cls.model_fields if k != "has_pdf"},
                   has_pdf=bool(row.get("pdf_path")))


class InjectionDetail(InjectionSummary):
    """Détail complet d'une injection archivée."""

    texte: str | None = None
    metadata: dict = Field(default_factory=dict)
    pdf_path: str | None = None

    @classmethod
    def from_row(cls, row: dict) -> "InjectionDetail":
        import json

        metadata = {}
        raw = row.get("metadata_json")
        if raw:
            try:
                parsed = json.loads(raw)
                # Une métadonnée non-objet (liste, scalaire) est ignorée plutôt que
                # de faire échouer la sérialisation de toute la réponse.
                metadata = parsed if isinstance(parsed, dict) else {"_raw": parsed}
            except (ValueError, TypeError):
                metadata = {"_raw": raw}

        known = {k: row.get(k) for k in cls.model_fields
                 if k not in ("has_pdf", "metadata")}
        return cls(**known, metadata=metadata, has_pdf=bool(row.get("pdf_path")))


class InjectionPage(BaseModel):
    """Page d'historique filtrée."""

    items: list[InjectionSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class InjectionFacets(BaseModel):
    """Valeurs disponibles pour les filtres de l'historique."""

    categories: list[str]
    arcs: list[str]


class InjectionResultOut(BaseModel):
    """Résultat d'une injection — renvoyé aussi bien en `201` qu'en `409`/`422`.

    Le journal d'exécution est toujours présent : c'est lui qui explique *pourquoi*
    une injection a échoué, et il vaut autant en cas d'erreur qu'en cas de succès.
    """

    success: bool
    messages: list[LogMessage]
    entry_number: int | None = None
    arc: str | None = None
    category: str | None = None
    xml_file: str | None = None
    injection_id: int | None = None
    has_pdf: bool = False
    duplicate: InjectionSummary | None = None
