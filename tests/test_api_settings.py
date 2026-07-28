"""Contrat HTTP de la page Paramètres.

Deux régressions sont verrouillées ici, toutes deux liées à « où vit la
configuration » :

  - la validation doit lire la configuration **effective** (variables
    d'environnement puis fichier), pas seulement le fichier — sinon une
    installation Docker parfaitement configurée est déclarée invalide ;
  - l'écriture doit viser `CONFIG_ENV_PATH`, pour pouvoir pointer le volume
    persistant au lieu de la couche d'image.
"""

import os

BASE = "/api/v1"


def test_settings_report_environment_provided_configuration_as_valid(client, sandbox):
    """Le fichier de config est vide : tout vient des variables d'environnement.

    C'est exactement la situation en conteneur (`env_file:` du docker-compose, et
    `.env` exclu par `.dockerignore`). L'ancienne implémentation répondait « Requis
    mais vide » et désactivait le bouton d'injection.
    """
    assert sandbox["config_env_path"].read_text(encoding="utf-8") == ""

    body = client.get(f"{BASE}/settings").json()

    assert body["all_ok"] is True
    by_key = {c["key"]: c for c in body["checks"]}
    assert by_key["FULL_CONTEXT_JSON_PATH"]["status"] == "ok"
    assert by_key["FULL_CONTEXT_JSON_PATH"]["value"] == str(sandbox["context_path"])


def test_settings_expose_the_file_actually_written(client, sandbox):
    body = client.get(f"{BASE}/settings").json()
    assert body["config_path"] == str(sandbox["config_env_path"])


def test_missing_required_path_is_flagged(unconfigured_client):
    body = unconfigured_client.get(f"{BASE}/settings").json()

    assert body["all_ok"] is False
    by_key = {c["key"]: c for c in body["checks"]}
    assert by_key["FULL_CONTEXT_JSON_PATH"]["status"] == "error"
    assert by_key["FULL_CONTEXT_JSON_PATH"]["message"] == "Requis mais vide"
    # Le champ optionnel n'est pas une erreur, il est simplement vide.
    assert by_key["METADATAS_DIR"]["status"] == "empty"


def test_nonexistent_path_is_flagged(client, sandbox):
    response = client.put(f"{BASE}/settings", json={"values": {
        **sandbox["values"],
        "TAKE_NOTES_EXPORT_DIR": str(sandbox["root"] / "nexiste-pas"),
    }})

    body = response.json()
    assert body["all_ok"] is False
    by_key = {c["key"]: c for c in body["checks"]}
    assert by_key["TAKE_NOTES_EXPORT_DIR"]["message"] == "Dossier introuvable"


def test_non_integer_token_width_is_flagged(client, sandbox):
    response = client.put(f"{BASE}/settings", json={"values": {
        **sandbox["values"], "MAX_TOKENS_PER_ENTRY": "beaucoup",
    }})

    by_key = {c["key"]: c for c in response.json()["checks"]}
    assert by_key["MAX_TOKENS_PER_ENTRY"]["message"] == "Doit être un entier"


def test_put_writes_to_the_configured_file(client, sandbox):
    client.put(f"{BASE}/settings", json={"values": {
        **sandbox["values"], "PDF_EXPORT_FILE": "JOURNAL",
    }})

    written = sandbox["config_env_path"].read_text(encoding="utf-8")
    assert "PDF_EXPORT_FILE=JOURNAL" in written
    assert client.get(f"{BASE}/settings").json()["all_ok"] is True


def test_put_ignores_unknown_keys(client, sandbox):
    """Une requête ne doit pas pouvoir écrire une variable arbitraire."""
    client.put(f"{BASE}/settings", json={"values": {
        **sandbox["values"], "SECRET_INJECTE": "malveillant",
    }})

    written = sandbox["config_env_path"].read_text(encoding="utf-8")
    assert "SECRET_INJECTE" not in written
    keys = {c["key"] for c in client.get(f"{BASE}/settings").json()["checks"]}
    assert "SECRET_INJECTE" not in keys


# --- Cohérence entre validation et chargement -----------------------------------

def test_paths_written_through_the_api_are_actually_used(tmp_path, monkeypatch):
    """Ce que la page Paramètres écrit doit être ce que le service charge.

    Régression : `EnvLoader` faisait un `load_dotenv()` sans argument, qui
    redécouvre le `.env` du dépôt en remontant depuis le répertoire courant. La
    validation jugeait `CONFIG_ENV_PATH` pendant que le chargement lisait un autre
    fichier — `/health` répondait « configuration valide » et l'injection échouait
    en 503 sur des chemins venus d'ailleurs. En production, les chemins saisis
    depuis l'interface n'auraient jamais été lus.
    """
    import shutil

    from fastapi.testclient import TestClient

    from backend.app.config import DeploymentSettings, get_deployment_settings
    from backend.app.main import create_app
    from tests.conftest import ENV_KEYS, SAMPLES_DIR

    # Aucune variable d'environnement : tout doit venir du fichier de configuration.
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    exports = tmp_path / "exports"
    entries = tmp_path / "entries"
    exports.mkdir()
    entries.mkdir()
    for name in os.listdir(SAMPLES_DIR):
        if name.endswith(".xml"):
            shutil.copy2(os.path.join(SAMPLES_DIR, name), exports / name)
    context = tmp_path / "full_context.json"
    context.write_text('{"character_arc": {}}', encoding="utf-8")

    config_env = tmp_path / "app.env"
    config_env.write_text("", encoding="utf-8")

    app = create_app()
    app.dependency_overrides[get_deployment_settings] = lambda: DeploymentSettings(
        database_path=str(tmp_path / "injections.db"),
        keybinds_db_path=str(tmp_path / "keybinds.db"),
        config_env_path=str(config_env),
        dev_cors_origin="",
    )

    with TestClient(app) as client:
        assert client.get(f"{BASE}/health").json()["config_ok"] is False

        saved = client.put(f"{BASE}/settings", json={"values": {
            "FULL_CONTEXT_JSON_PATH": str(context),
            "ENTRIES_DIR": str(entries),
            "TAKE_NOTES_EXPORT_DIR": str(exports),
        }}).json()
        assert saved["all_ok"] is True

        # Et surtout : le service charge bien ces chemins-là.
        assert client.get(f"{BASE}/health").json()["config_ok"] is True
        response = client.post(f"{BASE}/injections", json={
            "category": "quetes", "text": "Texte.", "generate_pdf": False,
        })
        assert response.status_code == 201, response.text

    app.dependency_overrides.clear()
