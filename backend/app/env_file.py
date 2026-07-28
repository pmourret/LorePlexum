"""Lecture / écriture / validation de la configuration applicative éditable.

Reprend l'ancien `webapp/settings.py` avec une différence : le chemin du fichier
n'est plus une constante de module mais un paramètre, fourni par
`DeploymentSettings.config_env_path`. C'est ce qui permet de le placer sur le
volume persistant en conteneur au lieu de la couche d'image (voir `config.py`).

Les valeurs écrites sont aussi poussées dans `os.environ` : `EnvLoader`, relu à
chaque requête, les prend en compte sans redémarrage.
"""

import os

from dotenv import dotenv_values, set_key, load_dotenv

# Description des champs de configuration : (clé, libellé, type de chemin, requis).
# `kind` : 'file' / 'dir' -> vérification d'existence ; None -> pas de vérif chemin.
FIELDS = [
    ("FULL_CONTEXT_JSON_PATH", "JSON de contexte complet", "file", True),
    ("ENTRIES_DIR", "Dossier des textes enrichis", "dir", True),
    ("METADATAS_DIR", "Dossier des métadonnées (facultatif, hérité V1)", "dir", False),
    ("TAKE_NOTES_EXPORT_DIR", "Dossier des exports XML TakeNotes", "dir", True),
    ("PDF_OUTPUT_PATH", "Dossier de sortie des PDF", "dir", False),
    ("PDF_EXPORT_FILE", "Préfixe du nom de fichier PDF", None, False),
    ("MAX_TOKENS_PER_ENTRY", "Largeur max d'un segment XML", None, False),
]

FIELD_KEYS = [key for key, *_ in FIELDS]


def read_file_settings(env_path):
    """Retourne le dict {clé: valeur} du fichier seul (vide s'il n'existe pas)."""
    if not os.path.exists(env_path):
        return {}
    return {k: (v or "") for k, v in dotenv_values(env_path).items()}


def effective_settings(env_path):
    """Configuration **réellement** vue par `EnvLoader`, dans son ordre de priorité.

    `EnvLoader` appelle `load_dotenv()` (qui n'écrase pas l'existant) puis lit
    `os.getenv` : une variable d'environnement l'emporte donc sur le fichier.

    C'est la distinction que l'ancienne implémentation manquait, et elle comptait :
    en conteneur, la configuration est injectée par `env_file:` (docker-compose) et
    le `.env` est exclu de l'image par `.dockerignore`. La validation, qui ne lisait
    que le fichier, déclarait donc « Requis mais vide » et désactivait le bouton
    d'injection sur une installation pourtant parfaitement configurée.
    """
    from_file = read_file_settings(env_path)
    return {
        key: (os.environ.get(key) or from_file.get(key) or "")
        for key in FIELD_KEYS
    }


def save_settings(env_path, values):
    """Écrit les valeurs fournies dans le fichier de configuration.

    Crée le fichier et son dossier parent si nécessaire — en conteneur, le volume
    est monté vide au premier démarrage. Recharge ensuite les valeurs dans
    l'environnement du process pour qu'elles s'appliquent sans redémarrage.
    """
    parent = os.path.dirname(os.path.abspath(env_path))
    os.makedirs(parent, exist_ok=True)
    if not os.path.exists(env_path):
        open(env_path, "a", encoding="utf-8").close()

    for key in FIELD_KEYS:
        value = (values.get(key) or "").strip()
        # quote_mode="never" : chemins réseau Windows lisibles tels quels dans le fichier.
        set_key(env_path, key, value, quote_mode="never")
        os.environ[key] = value

    load_dotenv(env_path, override=True)


def validate_settings(env_path=None, values=None):
    """Valide les champs et l'existence des chemins.

    Retourne (ok, checks) où checks est une liste de dicts prêts à afficher :
    {key, label, value, required, kind, status, message}. status ∈ {ok, error, empty}.
    """
    if values is None:
        values = effective_settings(env_path) if env_path else {}
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
