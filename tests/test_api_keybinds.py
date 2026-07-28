"""Contrat HTTP de la carte des touches."""

from backend.core import keyboard_layout as keyboard

BASE = "/api/v1"


def test_keymap_returns_layout_categories_and_binds_in_one_call(client):
    body = client.get(f"{BASE}/keymap").json()

    layout = body["layout"]
    assert len(layout["rows"]) == 6
    assert len(layout["numpad"]) == 3
    assert len(layout["mouse_buttons"]) == 3
    assert len(layout["mouse_side"]) == 2

    # Les scan codes sont positionnels : la touche A d'un AZERTY porte le code 16
    # (le « Q » américain). C'est la confusion que le module neutralise.
    row_a = {k["legend"]: k["code"] for k in layout["rows"][2]}
    assert row_a["A"] == 16
    assert row_a["Z"] == 17

    assert [c["key"] for c in body["categories"]] == list(keyboard.CATEGORIES)
    assert all({"ink", "edge", "face"} <= c.keys() for c in body["categories"])


def test_keymap_is_seeded_with_the_default_mapping(client):
    body = client.get(f"{BASE}/keymap").json()

    binds = {b["scan_code"]: b for b in body["binds"]}
    assert len(binds) == len(keyboard.DEFAULT_BINDS)
    assert binds[17]["action"] == "Avancer"
    assert binds[17]["cat"] == "deplacement"
    assert body["counts"]["deplacement"] == 8
    assert body["free_count"] > 0


def test_setting_a_bind_persists_and_updates_counters(client):
    response = client.put(f"{BASE}/keybinds/25", json={
        "action": "Journal", "cat": "interface", "note": "MCM SkyUI.",
    })

    assert response.status_code == 200
    assert response.json() == {
        "scan_code": 25, "action": "Journal", "cat": "interface",
        "note": "MCM SkyUI.", "updated_at": response.json()["updated_at"],
    }

    keymap = client.get(f"{BASE}/keymap").json()
    binds = {b["scan_code"]: b for b in keymap["binds"]}
    assert binds[25]["action"] == "Journal"
    assert keymap["counts"]["interface"] == 1


def test_reassigning_a_key_overwrites_it(client):
    """« Une touche = une action » est garanti par le schéma (clé primaire)."""
    client.put(f"{BASE}/keybinds/25", json={"action": "Journal", "cat": "interface"})
    client.put(f"{BASE}/keybinds/25", json={"action": "Carte", "cat": "vanilla"})

    binds = {b["scan_code"]: b for b in client.get(f"{BASE}/keymap").json()["binds"]}
    assert binds[25]["action"] == "Carte"
    assert binds[25]["cat"] == "vanilla"


def test_unknown_category_is_refused_instead_of_silently_ignored(client):
    """L'ancienne route HTML ignorait une famille inconnue : le formulaire semblait
    accepté alors que rien n'était écrit. Ici c'est un refus explicite."""
    response = client.put(f"{BASE}/keybinds/25", json={
        "action": "Journal", "cat": "famille-inexistante",
    })

    assert response.status_code == 422
    binds = {b["scan_code"] for b in client.get(f"{BASE}/keymap").json()["binds"]}
    assert 25 not in binds


def test_empty_action_is_rejected(client):
    assert client.put(f"{BASE}/keybinds/25",
                      json={"action": "", "cat": "interface"}).status_code == 422


def test_clearing_a_key_frees_it_and_is_idempotent(client):
    assert client.delete(f"{BASE}/keybinds/17").status_code == 204

    binds = {b["scan_code"] for b in client.get(f"{BASE}/keymap").json()["binds"]}
    assert 17 not in binds

    # Libérer une touche déjà libre n'est pas une erreur.
    assert client.delete(f"{BASE}/keybinds/17").status_code == 204


def test_export_is_sorted_and_offered_as_a_download(client):
    response = client.get(f"{BASE}/keybinds/export")

    assert response.status_code == 200
    assert "carte-des-touches.json" in response.headers["content-disposition"]

    body = response.json()
    codes = [b["scan_code"] for b in body["binds"]]
    assert codes == sorted(codes), "l'export doit être trié pour un diff lisible"
    assert body["count"] == len(body["binds"])
