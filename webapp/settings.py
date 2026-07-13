"""Lecture / écriture / validation du fichier .env depuis l'interface web.

Remplace l'édition manuelle du .env : la page « Paramètres » lit ces valeurs, les
affiche dans un formulaire, les revalide en direct (chemins existants ou non) et
les réécrit. On manipule le .env réel à la racine du projet.
"""

import os
from dotenv import dotenv_values, set_key, load_dotenv

# Racine du projet (…/TNFCDataInjector_v2), le .env y vit.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# Description des champs de configuration : (clé, libellé, type de chemin, requis).
# `kind` : 'file' / 'dir' -> vérification d'existence ; None -> pas de vérif chemin.
FIELDS = [
    ("FULL_CONTEXT_JSON_PATH", "JSON de contexte complet", "file", True),
    ("ENTRIES_DIR", "Dossier des textes enrichis", "dir", True),
    ("METADATAS_DIR", "Dossier des métadonnées", "dir", True),
    ("TAKE_NOTES_EXPORT_DIR", "Dossier des exports XML TakeNotes", "dir", True),
    ("PDF_OUTPUT_PATH", "Dossier de sortie des PDF", "dir", False),
    ("PDF_EXPORT_FILE", "Préfixe du nom de fichier PDF", None, False),
    ("MAX_TOKENS_PER_ENTRY", "Largeur max d'un segment XML", None, False),
]


def read_settings():
    """Retourne le dict {clé: valeur} courant du .env (vide si absent)."""
    if not os.path.exists(ENV_PATH):
        return {}
    return {k: (v or "") for k, v in dotenv_values(ENV_PATH).items()}


def save_settings(values):
    """Écrit les valeurs fournies dans le .env (création si nécessaire).

    Recharge ensuite le .env dans l'environnement du process pour que les nouvelles
    valeurs soient prises en compte sans redémarrage.
    """
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH, "a", encoding="utf-8").close()
    for key, _label, _kind, _required in FIELDS:
        value = (values.get(key) or "").strip()
        # quote_mode="never" : chemins réseau Windows lisibles tels quels dans le .env.
        set_key(ENV_PATH, key, value, quote_mode="never")
        os.environ[key] = value
    load_dotenv(ENV_PATH, override=True)


def validate_settings(values=None):
    """Valide les champs et l'existence des chemins.

    Retourne (ok, checks) où checks est une liste de dicts prêts à afficher :
    {key, label, value, required, kind, status, message}. status ∈ {ok, error, empty}.
    """
    values = values if values is not None else read_settings()
    checks = []
    all_ok = True
    for key, label, kind, required in FIELDS:
        value = (values.get(key) or "").strip()
        status, message = "ok", "OK"

        if not value:
            if required:
                status, message = "error", "Requis mais vide"
                all_ok = False
            else:
                status, message = "empty", "Optionnel (non renseigné)"
        elif kind == "file":
            if not os.path.isfile(value):
                status, message = "error", "Fichier introuvable"
                all_ok = False
        elif kind == "dir":
            if not os.path.isdir(value):
                status, message = "error", "Dossier introuvable"
                all_ok = False
        elif key == "MAX_TOKENS_PER_ENTRY" and value:
            if not value.isdigit():
                status, message = "error", "Doit être un entier"
                all_ok = False

        checks.append({
            "key": key, "label": label, "value": value,
            "required": required, "kind": kind,
            "status": status, "message": message,
        })
    return all_ok, checks
