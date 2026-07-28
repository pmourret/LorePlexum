"""Carte des touches : disposition, assignations, export."""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse

from backend.app.deps import KeysDb
from backend.app.schemas.keys import (
    Key,
    KeyBind,
    KeyBindWrite,
    KeyCategory,
    KeyboardLayoutOut,
    KeymapOut,
)
from backend.core import keyboard_layout as keyboard

router = APIRouter(tags=["keybinds"])

ScanCode = Path(description="Scan code DirectInput de la touche")


def _categories() -> list[KeyCategory]:
    return [KeyCategory(key=key, **cat) for key, cat in keyboard.CATEGORIES.items()]


@router.get("/keymap", response_model=KeymapOut,
            summary="État complet de la carte des touches")
def get_keymap(keys_db: KeysDb) -> KeymapOut:
    """Disposition, familles, assignations et compteurs — en un seul appel.

    Le client dispose ainsi de tout l'état : filtrer par famille, chercher une
    action ou ouvrir l'éditeur d'une touche ne demande plus d'aller-retour serveur.
    """
    binds = keys_db.all_binds()
    return KeymapOut(
        layout=KeyboardLayoutOut(
            rows=[[Key(**k) for k in row] for row in keyboard.ROWS],
            numpad=[[Key(**k) for k in row] for row in keyboard.NUMPAD],
            mouse_buttons=[Key(**k) for k in keyboard.MOUSE_BUTTONS],
            mouse_side=[Key(**k) for k in keyboard.MOUSE_SIDE],
        ),
        categories=_categories(),
        free_key=KeyCategory(key="", **keyboard.FREE_KEY),
        binds=[KeyBind(**b) for b in binds.values()],
        counts=keys_db.count_by_category(),
        free_count=sum(1 for k in keyboard.all_keys() if k["code"] not in binds),
    )


@router.put("/keybinds/{scan_code}", response_model=KeyBind,
            summary="Assigne (ou réassigne) une touche",
            responses={422: {"description": "Famille inconnue"}})
def set_keybind(payload: KeyBindWrite, keys_db: KeysDb, scan_code: int = ScanCode) -> KeyBind:
    """Une famille inconnue est refusée plutôt qu'écrite en base.

    L'ancienne route l'ignorait silencieusement : le formulaire semblait accepté
    mais rien n'était enregistré.
    """
    if payload.cat not in keyboard.CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Famille inconnue : {payload.cat}. "
                   f"Attendu : {', '.join(keyboard.CATEGORIES)}.",
        )

    keys_db.set_bind(scan_code, payload.action, payload.cat, payload.note)
    bind = keys_db.get_bind(scan_code)
    return KeyBind(**bind)


@router.delete("/keybinds/{scan_code}", status_code=204,
               summary="Libère une touche")
def clear_keybind(keys_db: KeysDb, scan_code: int = ScanCode) -> None:
    """Idempotent : libérer une touche déjà libre n'est pas une erreur."""
    keys_db.clear_bind(scan_code)


@router.get("/keybinds/export", response_class=JSONResponse,
            summary="Exporte la carte complète en JSON")
def export_keybinds(keys_db: KeysDb) -> JSONResponse:
    return JSONResponse(
        keys_db.export_payload(),
        headers={"Content-Disposition": 'attachment; filename="carte-des-touches.json"'},
    )
