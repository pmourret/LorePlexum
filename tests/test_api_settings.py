"""Contrat HTTP de la page Paramètres.

Deux régressions sont verrouillées ici, toutes deux liées à « où vit la
configuration » :

  - la validation doit lire la configuration **effective** (variables
    d'environnement puis fichier), pas seulement le fichier — sinon une
    installation Docker parfaitement configurée est déclarée invalide ;
  - l'écriture doit viser `CONFIG_ENV_PATH`, pour pouvoir pointer le volume
    persistant au lieu de la couche d'image.
"""

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
