"""Tests de l'orchestrateur — surtout de ses invariants.

`InjectionService` porte la garantie la plus importante du projet : le JSON de
contexte n'est écrit sur disque **qu'après** le succès de l'injection XML, pour que
les deux fichiers ne divergent jamais. Cette garantie n'était couverte par aucun
test avant ce refactor ; elle l'est ici en premier.
"""

import json

from backend.core.injection_service import InjectionRequest


def read_context(sandbox):
    return json.loads(sandbox["context_path"].read_text(encoding="utf-8"))


def journals(context, arc):
    return context["character_arc"][arc]["journals"]


def make_request(**overrides):
    payload = {
        "category": "quetes",
        "resume": "Un résumé.",
        "text": "Le corps du journal enrichi.",
        "generate_pdf": False,
    }
    payload.update(overrides)
    return InjectionRequest(**payload)


# --- Chemin nominal -------------------------------------------------------------

def test_successful_injection_writes_both_json_and_xml(service, sandbox):
    result = service.run(make_request(entry_date="First Seed, 1st, 4E 202"))

    assert result.success
    assert result.entry_number == 1
    assert result.arc == "arc_1"
    assert result.xml_file == "ExportChapter3.xml"

    context = read_context(sandbox)
    assert journals(context, "arc_1")[0]["text"] == "Le corps du journal enrichi."
    assert journals(context, "arc_1")[0]["summary"] == "Un résumé."

    xml = (sandbox["export_dir"] / "ExportChapter3.xml").read_text(encoding="utf-8")
    assert "Le corps du journal enrichi." in xml


def test_injection_is_archived_in_database(service, db):
    result = service.run(make_request())

    assert result.injection_id is not None
    row = db.get_injection(result.injection_id)
    assert row["categorie"] == "quetes"
    assert row["texte"] == "Le corps du journal enrichi."
    assert row["hash_texte"]


def test_second_injection_appends_to_same_arc(service, sandbox):
    service.run(make_request(text="Première entrée."))
    result = service.run(make_request(text="Deuxième entrée.", arc="arc_1"))

    assert result.entry_number == 2
    assert len(journals(read_context(sandbox), "arc_1")) == 2


def test_injection_without_arc_always_creates_a_new_one(service, sandbox):
    """Sans arc explicite, chaque injection ouvre un arc auto-numéroté.

    Comportement voulu mais contre-intuitif : deux injections d'affilée sans
    toucher au menu « arc » ne se suivent pas, elles ouvrent arc_1 puis arc_2.
    """
    assert service.run(make_request(text="Premier.")).arc == "arc_1"
    assert service.run(make_request(text="Second.")).arc == "arc_2"
    assert list(read_context(sandbox)["character_arc"]) == ["arc_1", "arc_2"]


def test_named_arc_is_created_when_unknown(service, sandbox):
    result = service.run(make_request(arc="arc_prologue"))

    assert result.arc == "arc_prologue"
    assert "arc_prologue" in read_context(sandbox)["character_arc"]


# --- L'invariant : pas de JSON sans XML -----------------------------------------

def test_json_is_not_saved_when_xml_injection_fails(service, sandbox):
    """Le cœur du sujet : un échec XML ne doit laisser aucune trace dans le JSON.

    On supprime le fichier d'export ciblé pour faire échouer l'étape XML après que
    l'entrée a déjà été ajoutée à la structure JSON **en mémoire**. Le fichier sur
    disque doit rester intact.
    """
    before = sandbox["context_path"].read_text(encoding="utf-8")
    (sandbox["export_dir"] / "ExportChapter3.xml").unlink()

    result = service.run(make_request())

    assert not result.success
    assert sandbox["context_path"].read_text(encoding="utf-8") == before
    assert read_context(sandbox)["character_arc"] == {}

    levels = [m["message"] for m in result.messages if m["level"] == "error"]
    assert any("synchronis" in m for m in levels), levels


# --- Anti-doublon ---------------------------------------------------------------

def test_duplicate_text_is_refused_without_writing(service, sandbox):
    service.run(make_request(text="Texte unique."))
    context_after_first = sandbox["context_path"].read_text(encoding="utf-8")

    result = service.run(make_request(text="Texte unique."))

    assert not result.success
    assert result.duplicate is not None
    assert result.duplicate["categorie"] == "quetes"
    # Aucune écriture : le JSON est identique à ce qu'il était après la 1re injection.
    assert sandbox["context_path"].read_text(encoding="utf-8") == context_after_first


def test_allow_duplicate_forces_the_injection(service, sandbox):
    service.run(make_request(text="Texte unique.", arc="arc_1"))

    result = service.run(
        make_request(text="Texte unique.", arc="arc_1", allow_duplicate=True)
    )

    assert result.success
    assert len(journals(read_context(sandbox), "arc_1")) == 2


def test_duplicate_detection_ignores_surrounding_whitespace(service):
    service.run(make_request(text="Texte à empreinte."))

    result = service.run(make_request(text="   Texte à empreinte.\n  "))

    assert not result.success
    assert result.duplicate is not None


# --- Échecs propres -------------------------------------------------------------

def test_unknown_category_fails_without_raising(service, sandbox):
    result = service.run(make_request(category="inexistante"))

    assert not result.success
    assert result.entry_number is None
    assert read_context(sandbox)["character_arc"] == {}


def test_empty_text_fails_without_writing(service, sandbox):
    result = service.run(make_request(text="   "))

    assert not result.success
    assert read_context(sandbox)["character_arc"] == {}


def test_missing_resume_warns_but_succeeds(service):
    result = service.run(make_request(resume=""))

    assert result.success
    assert any(m["level"] == "warning" for m in result.messages)


# --- Lecture pour l'UI ----------------------------------------------------------

def test_list_arcs_reflects_injections(service):
    assert service.list_arcs() == []
    service.run(make_request(arc="arc_prologue"))
    assert service.list_arcs() == ["arc_prologue"]


def test_suggest_entry_date_reads_last_known_date(service):
    # ExportChapter5.xml (divers) porte une dernière date connue dans les samples.
    assert service.suggest_entry_date("divers") == "First Seed, 31st, 4E 202"
    # ExportChapter3.xml (quetes) est vide : aucune date à proposer.
    assert service.suggest_entry_date("quetes") == ""
    assert service.suggest_entry_date("inexistante") == ""
