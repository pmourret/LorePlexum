"""Garde-fou de l'ancienne interface HTMX pendant la phase 2.

Elle est vouée à disparaître page par page, mais elle doit rester utilisable tant
qu'elle est là : c'est toute la promesse de la migration en strangler. Ces tests
vérifient que chaque page se rend encore et disparaîtront avec elle.

À la différence des tests d'API, on ne peut pas passer par `dependency_overrides` :
`webapp/ui.py` appelle `get_deployment_settings()` directement, hors du cycle de
dépendances. On agit donc sur les variables d'environnement, après vidage du cache.
"""

import re

import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_deployment_settings
from backend.app.main import create_app


@pytest.fixture
def legacy_client(sandbox, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(sandbox["database_path"]))
    monkeypatch.setenv("KEYBINDS_DB_PATH", str(sandbox["keybinds_db_path"]))
    monkeypatch.setenv("CONFIG_ENV_PATH", str(sandbox["config_env_path"]))
    get_deployment_settings.cache_clear()

    app = create_app(legacy_ui=True)
    with TestClient(app) as client:
        yield client

    get_deployment_settings.cache_clear()


def test_root_redirects_to_the_injection_form(legacy_client):
    response = legacy_client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/inject"


@pytest.mark.parametrize("path", ["/inject", "/history", "/keys", "/settings"])
def test_pages_render(legacy_client, path):
    response = legacy_client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_injection_form_is_not_blocked_by_a_false_config_error(legacy_client):
    """La config vient des variables d'environnement : la page doit être utilisable.

    C'est la traduction visible du bug corrigé dans `env_file.effective_settings` —
    auparavant le bandeau « Configuration incomplète » s'affichait et le bouton
    « Injecter » était désactivé sur une installation Docker correcte.
    """
    html = legacy_client.get("/inject").text

    assert "Configuration incomplète" not in html
    assert "Ouvrir les paramètres" not in html

    # Le bouton doit être actif. On isole sa balise : chercher « disabled » dans
    # toute la page matcherait l'attribut HTMX `hx-disabled-elt`, toujours présent.
    button = re.search(r"<button id=\"submit-btn\".*?>", html, re.DOTALL)
    assert button is not None
    assert "disabled" not in button.group(0)


def test_static_assets_are_served(legacy_client):
    assert legacy_client.get("/static/style.css").status_code == 200


def test_legacy_and_api_coexist_on_the_same_app(legacy_client):
    assert legacy_client.get("/inject").status_code == 200
    assert legacy_client.get("/api/v1/health").json()["config_ok"] is True


def test_keys_page_lists_the_seeded_mapping(legacy_client):
    html = legacy_client.get("/keys").text
    assert "Avancer" in html
    assert "Déplacement" in html
