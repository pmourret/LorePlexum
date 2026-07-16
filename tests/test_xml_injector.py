"""Tests d'intégration de XMLInjector au-dessus de la couche pivot FISS.

On travaille sur des COPIES temporaires des exports de ``samples/`` : les
fichiers de référence ne sont jamais modifiés.
"""

import os
import shutil
import tempfile
import unittest

from src.FissDocument import FissDocument
from src.XMLInjector import XMLInjector

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")


class XMLInjectorTests(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.mkdtemp(prefix="fissinject_")
        for name in os.listdir(SAMPLES_DIR):
            if name.endswith(".xml"):
                shutil.copy2(os.path.join(SAMPLES_DIR, name), os.path.join(self.workdir, name))
        self.injector = XMLInjector(self.workdir)

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _load(self, name):
        return FissDocument.load(os.path.join(self.workdir, name))

    def test_get_last_date_reads_native_capital_date_tags(self):
        # Régression : l'ancien code lisait `date{N}` en minuscule et renvoyait ""
        # sur un vrai export du jeu (balises `Date{N}`).
        self.assertEqual(
            self.injector.get_last_date("ExportChapter5.xml"),
            "First Seed, 31st, 4E 202",
        )
        self.assertEqual(self.injector.get_last_date("ExportChapter3.xml"), "")

    def test_inject_into_empty_chapter_appends_and_recomputes_counter(self):
        self.injector.inject_text_in_xml(
            "Première entrée du chapitre.", "ExportChapter3.xml",
            entry_date="First Seed, 1st, 4E 202", max_tokens=500,
        )
        doc = self._load("ExportChapter3.xml")
        self.assertEqual(len(doc.entries), 1)
        self.assertEqual(doc.entries[0].date, "First Seed, 1st, 4E 202")
        self.assertEqual(doc.number_of_entries, 2)  # 1 entrée + 1

    def test_inject_appends_to_multi_entry_chapter(self):
        before = len(self._load("ExportChapter1.xml").entries)  # 5
        self.injector.inject_text_in_xml(
            "Nouvelle page du journal.", "ExportChapter1.xml",
            entry_date="Sun's Dawn, 2nd, 4E 202", max_tokens=500,
        )
        doc = self._load("ExportChapter1.xml")
        self.assertEqual(len(doc.entries), before + 1)
        self.assertEqual(doc.entries[-1].text, "Nouvelle page du journal.")
        self.assertEqual(doc.number_of_entries, before + 2)

    def test_inject_falls_back_to_last_known_date(self):
        # entry_date vide -> reprend la dernière date connue du chapitre.
        self.injector.inject_text_in_xml(
            "Suite sans date fournie.", "ExportChapter5.xml", entry_date="", max_tokens=500,
        )
        doc = self._load("ExportChapter5.xml")
        self.assertEqual(doc.entries[-1].date, "First Seed, 31st, 4E 202")

    def test_long_text_is_segmented_into_multiple_entries(self):
        long_text = "mot " * 400  # bien au-delà de max_tokens=100
        self.injector.inject_text_in_xml(
            long_text, "ExportChapter3.xml", entry_date="Date", max_tokens=100,
        )
        doc = self._load("ExportChapter3.xml")
        self.assertGreater(len(doc.entries), 1)
        self.assertEqual(doc.number_of_entries, len(doc.entries) + 1)

    def test_todo_entry_is_replaced_in_priority(self):
        # On sème une entrée TODO puis on vérifie qu'elle est remplacée, pas ajoutée.
        doc = self._load("ExportChapter3.xml")
        from src.FissDocument import FissEntry
        doc.entries.append(FissEntry(date="Jour", text="TODO: à compléter"))
        doc.save(os.path.join(self.workdir, "ExportChapter3.xml"), backup=False)

        self.injector.inject_text_in_xml(
            "Contenu définitif.", "ExportChapter3.xml", entry_date="Jour", max_tokens=500,
        )
        result = self._load("ExportChapter3.xml")
        self.assertEqual(len(result.entries), 1)  # remplacée, pas ajoutée
        self.assertEqual(result.entries[0].text, "Contenu définitif.")

    def test_inject_writes_native_format_and_backup(self):
        self.injector.inject_text_in_xml(
            "Entrée native.", "ExportChapter2.xml", entry_date="Jour", max_tokens=500,
        )
        with open(os.path.join(self.workdir, "ExportChapter2.xml"), "rb") as handle:
            data = handle.read()
        self.assertFalse(data.startswith(b"<?xml"))
        self.assertNotIn(b"\n", data)
        # Un backup .bak a dû être créé (le fichier existait avant l'injection).
        backups = [f for f in os.listdir(self.workdir) if ".bak" in f]
        self.assertTrue(backups)

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            self.injector.inject_text_in_xml("", "ExportChapter1.xml")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.injector.inject_text_in_xml("x", "DoesNotExist.xml")


if __name__ == "__main__":
    unittest.main()
