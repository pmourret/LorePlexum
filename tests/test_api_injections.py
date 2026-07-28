"""Contrat HTTP du pipeline d'injection et de l'historique.

Ce qui est vérifié ici, ce n'est pas la logique métier (couverte par
`test_injection_service`) mais la **traduction** en HTTP : les codes de statut, la
forme des corps de réponse, et le fait qu'un doublon ou une configuration absente
ne se présentent pas comme une erreur interne.
"""

BASE = "/api/v1"


def payload(**overrides):
    body = {
        "category": "quetes",
        "resume": "Un résumé.",
        "text": "Le corps du journal enrichi.",
        "generate_pdf": False,
    }
    body.update(overrides)
    return body


# --- POST /injections -----------------------------------------------------------

def test_create_injection_returns_201_with_execution_log(client):
    response = client.post(f"{BASE}/injections", json=payload())

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["entry_number"] == 1
    assert body["arc"] == "arc_1"
    assert body["xml_file"] == "ExportChapter3.xml"
    assert body["injection_id"] is not None
    assert body["messages"], "le journal d'exécution doit toujours être présent"


def test_entry_date_components_are_assembled_into_stored_form(client):
    client.post(f"{BASE}/injections", json=payload(
        entry_date={"era": 4, "year": 201, "month_index": 11, "day": 15},
    ))

    detail = client.get(f"{BASE}/injections/1").json()
    assert detail["date_session"] == "Evening Star, 15th, 4E 201"


def test_day_out_of_month_range_is_clamped(client):
    # Le 31 n'existe pas en Sun's Dawn (28 jours) : ramené au dernier jour.
    client.post(f"{BASE}/injections", json=payload(
        entry_date={"era": 4, "year": 201, "month_index": 1, "day": 31},
    ))

    assert client.get(f"{BASE}/injections/1").json()["date_session"] == \
        "Sun's Dawn, 28th, 4E 201"


def test_duplicate_returns_409_with_the_existing_injection(client):
    client.post(f"{BASE}/injections", json=payload(text="Texte unique."))

    response = client.post(f"{BASE}/injections", json=payload(text="Texte unique."))

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["duplicate"]["categorie"] == "quetes"
    assert body["duplicate"]["entry_number"] == 1
    assert body["messages"]


def test_allow_duplicate_replays_successfully(client):
    client.post(f"{BASE}/injections", json=payload(text="Texte unique.", arc="a"))

    response = client.post(f"{BASE}/injections", json=payload(
        text="Texte unique.", arc="a", allow_duplicate=True,
    ))

    assert response.status_code == 201
    assert response.json()["entry_number"] == 2


def test_unknown_category_is_422(client):
    response = client.post(f"{BASE}/injections", json=payload(category="inexistante"))

    assert response.status_code == 422
    assert "inexistante" in response.json()["detail"]


def test_blank_text_is_rejected_by_validation(client):
    assert client.post(f"{BASE}/injections", json=payload(text="   ")).status_code == 422
    assert client.post(f"{BASE}/injections", json=payload(text="")).status_code == 422


def test_pipeline_failure_returns_500_with_the_log(client, sandbox):
    (sandbox["export_dir"] / "ExportChapter3.xml").unlink()

    response = client.post(f"{BASE}/injections", json=payload())

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert any(m["level"] == "error" for m in body["messages"])


def test_injection_fails_with_503_when_unconfigured(unconfigured_client):
    """Configuration absente -> 503, pas 500 : le client doit pouvoir distinguer."""
    response = unconfigured_client.post(f"{BASE}/injections", json=payload())

    assert response.status_code == 503
    assert response.json()["code"] == "configuration_invalid"


# --- GET /injections ------------------------------------------------------------

def test_history_is_paginated_and_filterable(client):
    for i in range(3):
        client.post(f"{BASE}/injections", json=payload(text=f"Entrée {i}.", arc="alpha"))
    client.post(f"{BASE}/injections", json=payload(
        category="journal", text="Autre catégorie.", arc="beta",
    ))

    page = client.get(f"{BASE}/injections", params={"per_page": 2}).json()
    assert page["total"] == 4
    assert page["total_pages"] == 2
    assert len(page["items"]) == 2

    filtered = client.get(f"{BASE}/injections", params={"categorie": "journal"}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["arc"] == "beta"

    searched = client.get(f"{BASE}/injections", params={"search": "Entrée 1"}).json()
    assert searched["total"] == 1


def test_history_rows_expose_pdf_availability_not_server_paths(client):
    client.post(f"{BASE}/injections", json=payload())

    item = client.get(f"{BASE}/injections").json()["items"][0]
    assert item["has_pdf"] is False
    assert "pdf_path" not in item


def test_facets_list_categories_and_known_arcs(client):
    client.post(f"{BASE}/injections", json=payload(arc="arc_prologue"))

    facets = client.get(f"{BASE}/injections/facets").json()
    assert "quetes" in facets["categories"]
    assert facets["arcs"] == ["arc_prologue"]


# --- GET /injections/{id} -------------------------------------------------------

def test_detail_returns_full_text_and_parsed_metadata(client):
    client.post(f"{BASE}/injections", json=payload(
        metadata={"lieu": "Bordeciel", "emotion": "tension"},
    ))

    detail = client.get(f"{BASE}/injections/1").json()
    assert detail["texte"] == "Le corps du journal enrichi."
    assert detail["metadata"] == {"lieu": "Bordeciel", "emotion": "tension"}


def test_unknown_injection_is_404(client):
    assert client.get(f"{BASE}/injections/999").status_code == 404


def test_pdf_download_is_404_when_never_generated(client):
    client.post(f"{BASE}/injections", json=payload())

    response = client.get(f"{BASE}/injections/1/pdf")
    assert response.status_code == 404
    assert "généré" in response.json()["detail"]
