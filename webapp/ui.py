"""Ancienne interface HTMX — **en sursis**.

Conservée le temps de la phase 2 du refactor, pendant laquelle la SPA React reprend
les pages une par une. Chaque page migrée retire les routes correspondantes d'ici ;
quand il ne reste rien, `webapp/` disparaît et `create_app(legacy_ui=False)` devient
le défaut.

N'ajoutez **rien** ici : toute évolution fonctionnelle va dans `backend/app/routers/`
et dans le frontend. Ce module a été converti de `FastAPI()` en `APIRouter` pour que
l'API et l'UI vivent sur une seule application, et il ne construit plus ses propres
bases de données : il consomme les dépendances de `backend.app.deps`, comme l'API.
"""

import os
import json

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app import env_file
from backend.app.config import get_deployment_settings
from backend.app.deps import Db, KeysDb, get_db, get_reporter, get_service
from backend.core.injection_service import InjectionRequest, XML_FILES_MAPPING
from backend.core.files import FileChooser
from backend.core import tamrielic_calendar as calendar
from backend.core import keyboard_layout as keyboard

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def mount_legacy_ui(app: FastAPI) -> None:
    """Attache les pages HTMX et leurs assets à l'application principale."""
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(BASE_DIR, "static")),
        name="static",
    )
    app.include_router(router)


def _config_env_path():
    return get_deployment_settings().config_env_path


def build_service(reporter=None, db=None):
    """Instancie le service comme le fait l'API, hors du système de `Depends`.

    Les pages HTMX appellent le service en dehors du cycle de dépendances (dans des
    `try` de pré-vol), d'où ce passe-plat vers `deps.get_service`.
    """
    settings = get_deployment_settings()
    return get_service(
        settings,
        db if db is not None else get_db(settings),
        reporter if reporter is not None else get_reporter(),
    )


def config_error():
    """Retourne le message d'erreur de config, ou None si tout est valide."""
    ok, _ = env_file.validate_settings(_config_env_path())
    if ok:
        return None
    return "Configuration incomplète ou invalide. Renseignez les chemins dans Paramètres."


def _date_field_context(date_str):
    """Contexte du champ date (menus du calendrier tamrielien) pré-rempli.

    `date_str` est la dernière date connue de la catégorie (ou ""). On la décompose
    en composants pour pré-sélectionner ère / année / mois / jour.
    """
    sel = calendar.components_or_default(date_str)
    return {
        "eras": calendar.ERAS,
        "months": list(enumerate(calendar.month_names_en())),
        "sel": sel,
        # Bornes du menu « jour » ajustées au mois pré-sélectionné (voir /date-days).
        "max_day": calendar.days_in_month(sel["month_index"]),
        "sel_day": sel["day"],
    }


def _assemble_date(date_era, date_year, date_month, date_day):
    """Reconstruit la date stockée « Evening Star, 15th, 4E 201 » depuis les menus.

    Tolérant aux saisies vides/invalides : retombe alors sur les valeurs par défaut.
    """
    d = dict(calendar.DEFAULT)
    try:
        d["era"] = int(date_era)
        d["year"] = int(date_year)
        d["month_index"] = int(date_month)
        d["day"] = calendar.clamp_day(int(date_month), int(date_day))
    except (TypeError, ValueError):
        pass
    return calendar.format_date(d["era"], d["year"], d["month_index"], d["day"])


# --- Accueil -------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/inject")


# --- Injection -----------------------------------------------------------------

@router.get("/inject", response_class=HTMLResponse)
def inject_form(request: Request):
    err = config_error()
    categories = list(XML_FILES_MAPPING.keys())
    arcs, metadata_files, default_date = [], [], ""
    if not err:
        try:
            service = build_service()
            arcs = service.list_arcs()
            default_date = service.suggest_entry_date(categories[0])
            metadata_files = _safe_list_files(service.paths["metadatas_dir"])
        except Exception as e:
            err = f"Erreur de configuration : {e}"
    return templates.TemplateResponse("inject.html", {
        "request": request, "active": "inject", "config_error": err,
        "categories": categories, "arcs": arcs,
        "metadata_files": metadata_files, **_date_field_context(default_date),
    })


@router.get("/suggest-date", response_class=HTMLResponse)
def suggest_date(request: Request, category: str):
    """Renvoie le champ date pré-rempli avec la dernière date connue de la catégorie.

    Déclenché par HTMX au changement de catégorie.
    """
    value = ""
    try:
        value = build_service().suggest_entry_date(category)
    except Exception:
        pass
    return templates.TemplateResponse("_date_field.html", {
        "request": request, **_date_field_context(value),
    })


@router.get("/date-days", response_class=HTMLResponse)
def date_days(request: Request, date_month: int = 0, date_day: int = 1):
    """Renvoie le menu « jour » ajusté au mois choisi (28 à 31 jours).

    Déclenché par HTMX au changement de mois. Le jour courant est conservé, ramené
    au dernier jour du mois s'il le dépasse (ex. 31 en Sun's Dawn -> 28).
    """
    if not 0 <= date_month < len(calendar.MONTHS):
        date_month = 0
    return templates.TemplateResponse("_day_field.html", {
        "request": request,
        "max_day": calendar.days_in_month(date_month),
        "sel_day": calendar.clamp_day(date_month, date_day),
    })


@router.post("/inject", response_class=HTMLResponse)
def inject_submit(
    request: Request,
    category: str = Form(...),
    resume: str = Form(""),
    text: str = Form(""),
    arc_select: str = Form(""),
    new_arc: str = Form(""),
    metadata_file: str = Form(""),
    metadata_json: str = Form(""),
    date_era: str = Form(""),
    date_year: str = Form(""),
    date_month: str = Form(""),
    date_day: str = Form(""),
    allow_duplicate: str = Form(""),
):
    """Exécute une injection et renvoie le fragment de résultat (HTMX)."""
    reporter = get_reporter()

    err = config_error()
    if err:
        return _result_fragment(request, success=False, messages=[
            {"level": "error", "message": err}
        ])

    try:
        service = build_service(reporter)
    except Exception as e:
        return _result_fragment(request, success=False, messages=[
            {"level": "error", "message": f"Configuration invalide : {e}"}
        ])

    # Arc : un nom explicite prime ; sinon la sélection ; "" -> nouvel arc auto.
    arc = (new_arc.strip() or arc_select.strip()) or None

    # Métadonnées : fichier choisi prioritaire, sinon JSON collé, sinon {}.
    metadata, meta_err = _resolve_metadata(service, metadata_file, metadata_json)
    if meta_err:
        return _result_fragment(request, success=False, messages=[
            {"level": "error", "message": meta_err}
        ])

    # La date arrive découpée (menus du calendrier) : on la reconstitue en chaîne.
    entry_date = _assemble_date(date_era, date_year, date_month, date_day)

    req = InjectionRequest(
        category=category,
        resume=resume,
        text=text,
        metadata=metadata,
        arc=arc,
        entry_date=entry_date,
        allow_duplicate=bool(allow_duplicate),
    )
    result = service.run(req)

    return templates.TemplateResponse("_result.html", {
        "request": request,
        "result": result,
        # On renvoie les champs pour permettre le « forcer » sans re-saisie.
        "form": {
            "category": category, "resume": resume, "text": text,
            "arc_select": arc_select, "new_arc": new_arc,
            "metadata_file": metadata_file, "metadata_json": metadata_json,
            "date_era": date_era, "date_year": date_year,
            "date_month": date_month, "date_day": date_day,
        },
    })


# --- Historique ----------------------------------------------------------------

@router.get("/history", response_class=HTMLResponse)
def history(request: Request, db: Db, categorie: str = "", arc: str = "",
            search: str = "", page: int = 1):
    per_page = 20
    page = max(1, page)
    offset = (page - 1) * per_page
    filters = {
        "categorie": categorie or None,
        "arc": arc or None,
        "search": search or None,
    }
    items = db.list_injections(limit=per_page, offset=offset, **filters)
    total = db.count(**filters)
    total_pages = max(1, (total + per_page - 1) // per_page)

    ctx = {
        "request": request, "active": "history",
        "items": items, "total": total,
        "page": page, "total_pages": total_pages,
        "categories": list(XML_FILES_MAPPING.keys()),
        "arcs": db.distinct_arcs(),
        "f_categorie": categorie, "f_arc": arc, "f_search": search,
    }
    # Requête HTMX -> on ne renvoie que le tableau (mise à jour partielle).
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("_history_table.html", ctx)
    return templates.TemplateResponse("history.html", ctx)


@router.get("/injection/{injection_id}", response_class=HTMLResponse)
def injection_detail(request: Request, injection_id: int, db: Db):
    item = db.get_injection(injection_id)
    metadata_pretty = ""
    if item and item.get("metadata_json"):
        try:
            metadata_pretty = json.dumps(
                json.loads(item["metadata_json"]), ensure_ascii=False, indent=2
            )
        except Exception:
            metadata_pretty = item["metadata_json"]
    return templates.TemplateResponse("detail.html", {
        "request": request, "active": "history",
        "item": item, "metadata_pretty": metadata_pretty,
    })


@router.get("/pdf/{injection_id}")
def download_pdf(injection_id: int, db: Db):
    """Télécharge le PDF associé à une injection s'il existe encore sur disque."""
    item = db.get_injection(injection_id)
    if item and item.get("pdf_path") and os.path.isfile(item["pdf_path"]):
        return FileResponse(item["pdf_path"], filename=os.path.basename(item["pdf_path"]))
    return HTMLResponse("PDF introuvable.", status_code=404)


# --- Carte des touches ---------------------------------------------------------

def _keymap_context(request, keys_db, close_editor=False):
    """Contexte complet du partiel `_keyboard.html` (clavier, souris, légende).

    `close_editor` déclenche le swap hors-cible qui referme le panneau d'édition
    après une écriture : la réponse a déjà #keymap pour cible principale.
    """
    binds = keys_db.all_binds()
    return {
        "request": request,
        "rows": keyboard.ROWS,
        "numpad": keyboard.NUMPAD,
        "mouse_buttons": keyboard.MOUSE_BUTTONS,
        "mouse_side": keyboard.MOUSE_SIDE,
        "categories": keyboard.CATEGORIES,
        "free_key": keyboard.FREE_KEY,
        "palette": keyboard.palette,
        "binds": binds,
        "counts": keys_db.count_by_category(),
        # Touches déclarées dans la disposition et restées sans action.
        "free_count": sum(1 for k in keyboard.all_keys() if k["code"] not in binds),
        "close_editor": close_editor,
    }


@router.get("/keys", response_class=HTMLResponse)
def keys_page(request: Request, keys_db: KeysDb):
    return templates.TemplateResponse("keys.html", {
        **_keymap_context(request, keys_db), "active": "keys",
    })


@router.get("/keys/export")
def keys_export(keys_db: KeysDb):
    """Télécharge la carte complète en JSON (sauvegarde / partage)."""
    return JSONResponse(
        keys_db.export_payload(),
        headers={"Content-Disposition": 'attachment; filename="carte-des-touches.json"'},
    )


@router.get("/keys/{code}/edit", response_class=HTMLResponse)
def key_editor(request: Request, code: int, keys_db: KeysDb):
    """Panneau d'édition d'une touche (fragment HTMX)."""
    return templates.TemplateResponse("_key_editor.html", {
        "request": request,
        "code": code,
        "legend": keyboard.legend_of(code),
        "bind": keys_db.get_bind(code),
        "categories": keyboard.CATEGORIES,
        # Famille pré-cochée pour une touche libre : la première déclarée.
        "default_cat": next(iter(keyboard.CATEGORIES)),
    })


@router.post("/keys/{code}", response_class=HTMLResponse)
def key_save(request: Request, code: int, keys_db: KeysDb,
             action: str = Form(""), cat: str = Form(""), note: str = Form("")):
    """Assigne une touche, puis renvoie la carte à jour.

    Une action vide vaut libération : c'est le geste naturel quand on efface le
    champ. Une famille inconnue est ignorée plutôt qu'écrite en base.
    """
    if not action.strip():
        keys_db.clear_bind(code)
    elif cat in keyboard.CATEGORIES:
        keys_db.set_bind(code, action, cat, note)
    return templates.TemplateResponse(
        "_keyboard.html", _keymap_context(request, keys_db, close_editor=True)
    )


@router.post("/keys/{code}/clear", response_class=HTMLResponse)
def key_clear(request: Request, code: int, keys_db: KeysDb):
    """Libère une touche, puis renvoie la carte à jour."""
    keys_db.clear_bind(code)
    return templates.TemplateResponse(
        "_keyboard.html", _keymap_context(request, keys_db, close_editor=True)
    )


# --- Paramètres ----------------------------------------------------------------

@router.get("/settings", response_class=HTMLResponse)
def settings_form(request: Request, saved: str = ""):
    ok, checks = env_file.validate_settings(_config_env_path())
    return templates.TemplateResponse("settings.html", {
        "request": request, "active": "settings",
        "checks": checks, "all_ok": ok, "saved": bool(saved),
    })


@router.post("/settings", response_class=HTMLResponse)
async def settings_save(request: Request):
    form = await request.form()
    values = {key: form.get(key, "") for key in env_file.FIELD_KEYS}
    env_file.save_settings(_config_env_path(), values)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


# --- Helpers -------------------------------------------------------------------

def _safe_list_files(dir_path):
    try:
        return FileChooser.list_files(dir_path)
    except Exception:
        return []


def _resolve_metadata(service, metadata_file, metadata_json):
    """Retourne (metadata_dict, error_message)."""
    if metadata_file.strip():
        path = os.path.join(service.paths["metadatas_dir"], metadata_file.strip())
        try:
            return service.json_injector.load_metadata_json(path), None
        except Exception as e:
            return None, f"Métadonnées illisibles ({metadata_file}) : {e}"
    if metadata_json.strip():
        try:
            return json.loads(metadata_json), None
        except json.JSONDecodeError as e:
            return None, f"JSON de métadonnées invalide : {e}"
    return {}, None


def _result_fragment(request, success, messages):
    """Construit un fragment de résultat minimal (erreurs de pré-vol)."""
    from types import SimpleNamespace
    result = SimpleNamespace(
        success=success, messages=messages, entry_number=None, arc=None,
        category=None, xml_file=None, pdf_path=None, injection_id=None,
        duplicate=None,
    )
    return templates.TemplateResponse("_result.html", {
        "request": request, "result": result, "form": {},
    })
