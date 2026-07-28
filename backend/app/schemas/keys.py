"""Contrat d'API de la carte des touches.

`GET /api/v1/keymap` renvoie l'état complet — disposition, familles, assignations,
compteurs — en un seul appel. L'ancienne UI HTMX rechargeait le clavier entier à
chaque édition de touche ; avec l'état complet côté client, l'édition devient
locale et instantanée, et seule l'écriture part au serveur.
"""

from pydantic import BaseModel, Field


class KeyCategory(BaseModel):
    """Famille de touches : libellé et triplet de couleurs.

    Les couleurs viennent de `keyboard_layout.CATEGORIES` et remontent jusqu'aux
    variables CSS du keycap. Ajouter une famille reste une modification d'un seul
    fichier côté serveur : ni l'API ni le style n'en connaissent la liste.
    """

    key: str
    label: str
    ink: str = Field(description="Couleur du texte")
    edge: str = Field(description="Couleur du contour et de la bordure basse")
    face: str = Field(description="Couleur de fond")


class Key(BaseModel):
    """Une touche physique de la disposition."""

    code: int = Field(description="Scan code DirectInput (positionnel, pas la lettre)")
    legend: str
    width: float = Field(default=1, description="Largeur en unités de keycap")


class KeyBind(BaseModel):
    """Assignation d'une touche."""

    scan_code: int
    action: str
    cat: str
    note: str = ""
    updated_at: str | None = None


class KeyBindWrite(BaseModel):
    """Corps de `PUT /api/v1/keybinds/{scan_code}`."""

    action: str = Field(min_length=1)
    cat: str
    note: str = ""


class KeyboardLayoutOut(BaseModel):
    rows: list[list[Key]]
    numpad: list[list[Key]]
    mouse_buttons: list[Key]
    mouse_side: list[Key]


class KeymapOut(BaseModel):
    """État complet de la carte des touches."""

    layout: KeyboardLayoutOut
    categories: list[KeyCategory]
    free_key: KeyCategory
    binds: list[KeyBind]
    counts: dict[str, int] = Field(description="Nombre de touches par famille")
    free_count: int = Field(description="Touches déclarées et restées sans action")
