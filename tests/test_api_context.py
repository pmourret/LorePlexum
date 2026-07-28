"""Contrat HTTP des données de contexte : santé, catégories, arcs, calendrier."""

from backend.core import tamrielic_calendar as calendar

BASE = "/api/v1"


def test_health_reports_ok_when_configured(client):
    body = client.get(f"{BASE}/health").json()

    assert body["status"] == "ok"
    assert body["config_ok"] is True
    assert body["problems"] == []


def test_health_stays_reachable_when_unconfigured(unconfigured_client):
    """`/health` ne dépend pas du service : il doit répondre même config cassée.

    C'est ce qui permet au frontend de diagnostiquer et de rediriger vers les
    Paramètres au lieu d'afficher une page blanche.
    """
    response = unconfigured_client.get(f"{BASE}/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unconfigured"
    assert body["config_ok"] is False
    assert body["problems"]


def test_categories_expose_their_xml_target(client):
    categories = client.get(f"{BASE}/categories").json()

    by_key = {c["key"]: c["xml_file"] for c in categories}
    assert by_key["journal"] == "ExportChapter1.xml"
    assert by_key["quetes"] == "ExportChapter3.xml"
    assert len(categories) == 5


def test_arcs_reflect_the_context_json(client):
    assert client.get(f"{BASE}/arcs").json() == []

    client.post(f"{BASE}/injections", json={
        "category": "quetes", "text": "Texte.", "arc": "arc_prologue",
        "generate_pdf": False,
    })

    assert client.get(f"{BASE}/arcs").json() == ["arc_prologue"]


def test_metadata_files_are_empty_rather_than_erroring(client):
    """Le dossier de métadonnées est facultatif : vide n'est pas une erreur."""
    response = client.get(f"{BASE}/metadata-files")

    assert response.status_code == 200
    assert response.json() == []


def test_metadata_files_are_listed_when_present(client, sandbox):
    (sandbox["metadatas_dir"] / "combat.json").write_text("{}", encoding="utf-8")
    (sandbox["metadatas_dir"] / "voyage.json").write_text("{}", encoding="utf-8")

    assert client.get(f"{BASE}/metadata-files").json() == ["combat.json", "voyage.json"]


# --- Calendrier -----------------------------------------------------------------

def test_calendar_returns_every_month_with_its_length(client):
    body = client.get(f"{BASE}/calendar").json()

    assert body["eras"] == [1, 2, 3, 4]
    assert len(body["months"]) == 12
    assert len(body["weekdays"]) == 7

    first, second, last = body["months"][0], body["months"][1], body["months"][11]
    assert (first["name_en"], first["days"]) == ("Morning Star", 31)
    # Sun's Dawn et ses 28 jours : c'est cette donnée qui permet au client de
    # calculer les bornes du menu « jour » sans rappeler le serveur.
    assert (second["name_en"], second["days"]) == ("Sun's Dawn", 28)
    assert last["name_en"] == "Evening Star"

    assert body["default"] == calendar.DEFAULT


def test_suggest_date_uses_last_known_date_of_category(client):
    body = client.get(f"{BASE}/calendar/suggest", params={"category": "divers"}).json()

    assert body["source"] == "last_known"
    assert body["stored"] == "First Seed, 31st, 4E 202"
    assert body["date"] == {"era": 4, "year": 202, "month_index": 2, "day": 31}


def test_suggest_date_falls_back_to_default_on_empty_chapter(client):
    body = client.get(f"{BASE}/calendar/suggest", params={"category": "quetes"}).json()

    assert body["source"] == "default"
    assert body["date"] == calendar.DEFAULT


def test_suggest_date_rejects_unknown_category(client):
    response = client.get(f"{BASE}/calendar/suggest", params={"category": "nope"})
    assert response.status_code == 422


# --- Lecture d'un fichier de métadonnées ----------------------------------------

def test_metadata_file_content_is_returned(client, sandbox):
    (sandbox["metadatas_dir"] / "combat.json").write_text(
        '{"lieu": "Bordeciel", "emotion": "tension"}', encoding="utf-8"
    )

    body = client.get(f"{BASE}/metadata-files/combat.json").json()
    assert body == {"lieu": "Bordeciel", "emotion": "tension"}


def test_unknown_metadata_file_is_404(client):
    assert client.get(f"{BASE}/metadata-files/absent.json").status_code == 404


def test_metadata_file_name_cannot_escape_the_directory(client, sandbox):
    """Le nom est validé par appartenance à la liste réelle, pas par filtrage.

    Un chemin relatif ne correspond à aucune entrée listée : il sort en 404 sans
    qu'aucune lecture hors du dossier ne soit tentée.
    """
    secret = sandbox["root"] / "secret.json"
    secret.write_text('{"secret": true}', encoding="utf-8")

    for attempt in ("../secret.json", "..%2Fsecret.json", "%2e%2e%2fsecret.json"):
        response = client.get(f"{BASE}/metadata-files/{attempt}")
        assert response.status_code == 404, attempt
        assert "secret" not in response.text


def test_invalid_json_metadata_is_422(client, sandbox):
    (sandbox["metadatas_dir"] / "casse.json").write_text("{pas du json", encoding="utf-8")

    assert client.get(f"{BASE}/metadata-files/casse.json").status_code == 422


def test_non_object_metadata_is_422(client, sandbox):
    (sandbox["metadatas_dir"] / "liste.json").write_text("[1, 2, 3]", encoding="utf-8")

    assert client.get(f"{BASE}/metadata-files/liste.json").status_code == 422
