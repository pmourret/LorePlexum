"""Application web FastAPI (interface de TNFCDataInjector).

Sert un formulaire d'injection, une page d'historique (archivage SQLite) et une
page de paramètres. Toute la logique métier vit dans src/InjectionService : ces
routes ne font que collecter les entrées du formulaire, appeler le service et
rendre le résultat. HTMX gère l'interactivité (soumission sans rechargement,
confirmation de doublon, filtres d'historique) sans framework JS.
"""

import os
import json

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.Reporter import Reporter
from src.Database import InjectionDatabase
from src.InjectionService import InjectionService, InjectionRequest, XML_FILES_MAPPING
from src.EnvLoader import EnvLoader
from src.FileChooser import FileChooser
from src import TamrielicCalendar as calendar
from webapp import settings as settings_module

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="TNFCDataInjector — Abyssiaelle")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Base d'archivage partagée par toutes les requêtes (connexion ouverte par appel).
db = InjectionDatabase()


def build_service(reporter=None):
    """Instancie le service à partir du .env courant.

    Peut lever si la configuration est invalide (chemins manquants) : les routes
    attrapent et redirigent l'utilisateur vers la page Paramètres.
    """
    env = EnvLoader()
    return InjectionService(
        env.get_paths(), pdf_export_file=env.pdf_export_file,
        reporter=reporter or Reporter(), db=db,
    )


def config_error():
    """Retourne le message d'erreur de config, ou None si tout est valide."""
    ok, _ = settings_module.validate_settings()
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

@app.get("/", response_class=HTMLResponse)
def index():
    return RedirectResponse(url="/inject")


# --- Injection -----------------------------------------------------------------

@app.get("/inject", response_class=HTMLResponse)
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


@app.get("/suggest-date", response_class=HTMLResponse)
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


@app.get("/date-days", response_class=HTMLResponse)
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


@app.post("/inject", response_class=HTMLResponse)
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
    reporter = Reporter()

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

@app.get("/history", response_class=HTMLResponse)
def history(request: Request, categorie: str = "", arc: str = "",
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


@app.get("/injection/{injection_id}", response_class=HTMLResponse)
def injection_detail(request: Request, injection_id: int):
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


@app.get("/pdf/{injection_id}")
def download_pdf(injection_id: int):
    """Télécharge le PDF associé à une injection s'il existe encore sur disque."""
    item = db.get_injection(injection_id)
    if item and item.get("pdf_path") and os.path.isfile(item["pdf_path"]):
        return FileResponse(item["pdf_path"], filename=os.path.basename(item["pdf_path"]))
    return HTMLResponse("PDF introuvable.", status_code=404)


# --- Paramètres ----------------------------------------------------------------

@app.get("/settings", response_class=HTMLResponse)
def settings_form(request: Request, saved: str = ""):
    ok, checks = settings_module.validate_settings()
    return templates.TemplateResponse("settings.html", {
        "request": request, "active": "settings",
        "checks": checks, "all_ok": ok, "saved": bool(saved),
    })


@app.post("/settings", response_class=HTMLResponse)
async def settings_save(request: Request):
    form = await request.form()
    values = {key: form.get(key, "") for key, *_ in settings_module.FIELDS}
    settings_module.save_settings(values)
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
