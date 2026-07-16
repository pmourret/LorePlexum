"""Tests de la couche pivot FISS, adossés aux exports réels de ``samples/``.

Ces 5 fichiers ont été générés directement depuis le jeu, sans aucune édition
manuelle. Ils servent à la fois de référence de format et de jeu de test.

Cas couverts (exigés) :
  - chapitre vide (0 entrée) — Chapter3 / Chapter4 ;
  - chapitre à 1 entrée — Chapter2 ;
  - chapitre à plusieurs entrées — Chapter1 (5), Chapter5 (2) ;
  - recalcul correct de ``<NumberOfEntries>`` en sortie (= entrées réelles + 1).

Lancer :  python -m unittest discover -s tests
"""

import os
import unittest

from src.FissDocument import FissDocument, FissEntry, FissError

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")

# Nombre RÉEL d'entrées par chapitre (compté manuellement sur les exports bruts),
# à ne PAS confondre avec <NumberOfEntries> qui vaut ce nombre + 1.
EXPECTED_ENTRY_COUNTS = {
    "ExportChapter1.xml": 5,
    "ExportChapter2.xml": 1,
    "ExportChapter3.xml": 0,
    "ExportChapter4.xml": 0,
    "ExportChapter5.xml": 2,
}


def sample_path(name):
    return os.path.join(SAMPLES_DIR, name)


def read_sample(name):
    with open(sample_path(name), "r", encoding="utf-8") as handle:
        return handle.read()


class SampleParsingTests(unittest.TestCase):
    """Le scan séquentiel donne le VRAI compte, indépendamment de NumberOfEntries."""

    def test_empty_chapter_has_zero_entries(self):
        for name in ("ExportChapter3.xml", "ExportChapter4.xml"):
            with self.subTest(sample=name):
                doc = FissDocument.load(sample_path(name))
                self.assertEqual(doc.entries, [])

    def test_single_entry_chapter(self):
        doc = FissDocument.load(sample_path("ExportChapter2.xml"))
        self.assertEqual(len(doc.entries), 1)
        self.assertEqual(doc.entries[0].date, "Evening Star, 15th, 4E 201")
        self.assertIn("Morvunskar", doc.entries[0].text)
        # L'apostrophe échappée en &apos; doit être dé-échappée en lecture.
        self.assertIn("m'ont abusés", doc.entries[0].text)

    def test_multi_entry_chapters(self):
        doc1 = FissDocument.load(sample_path("ExportChapter1.xml"))
        self.assertEqual(len(doc1.entries), 5)

        doc5 = FissDocument.load(sample_path("ExportChapter5.xml"))
        self.assertEqual(len(doc5.entries), 2)
        # Deux dates distinctes dans Chapter5.
        self.assertEqual(doc5.entries[0].date, "Evening Star, 15th, 4E 201")
        self.assertEqual(doc5.entries[1].date, "First Seed, 31st, 4E 202")
        # &#x0D; (retour à la ligne natif) doit devenir un vrai \r en mémoire.
        self.assertIn("\r", doc5.entries[0].text)

    def test_scan_ignores_number_of_entries_for_counting(self):
        """Le compte vient du scan des paires, jamais de <NumberOfEntries>."""
        for name, expected in EXPECTED_ENTRY_COUNTS.items():
            with self.subTest(sample=name):
                doc = FissDocument.load(sample_path(name))
                self.assertEqual(len(doc.entries), expected)


class NumberOfEntriesTests(unittest.TestCase):
    """<NumberOfEntries> en SORTIE = entrées réelles + 1 (index de la prochaine)."""

    def test_recomputed_value_matches_next_index_convention(self):
        for name, real_count in EXPECTED_ENTRY_COUNTS.items():
            with self.subTest(sample=name):
                doc = FissDocument.load(sample_path(name))
                self.assertEqual(doc.number_of_entries, real_count + 1)

    def test_empty_chapter_serializes_number_of_entries_1(self):
        doc = FissDocument()  # 0 entrée
        self.assertIn("<NumberOfEntries>1</NumberOfEntries>", doc.serialize())

    def test_number_of_entries_increments_when_entry_added(self):
        doc = FissDocument.load(sample_path("ExportChapter2.xml"))  # 1 entrée -> 2
        self.assertEqual(doc.number_of_entries, 2)
        doc.entries.append(FissEntry(date="First Seed, 1st, 4E 202", text="Nouvelle."))
        self.assertEqual(doc.number_of_entries, 3)
        self.assertIn("<NumberOfEntries>3</NumberOfEntries>", doc.serialize())


class RoundTripTests(unittest.TestCase):
    """serialize() reproduit le format natif OCTET POUR OCTET."""

    def test_all_samples_round_trip_byte_exact(self):
        for name in EXPECTED_ENTRY_COUNTS:
            with self.subTest(sample=name):
                original = read_sample(name)
                doc = FissDocument.parse(original, source=name)
                self.assertEqual(doc.serialize(), original)

    def test_serialized_output_is_single_line_without_declaration(self):
        doc = FissDocument.load(sample_path("ExportChapter1.xml"))
        out = doc.serialize()
        self.assertNotIn("\n", out)
        self.assertNotIn("\r", out)
        self.assertFalse(out.startswith("<?xml"))
        self.assertTrue(out.startswith("<fiss>"))
        self.assertTrue(out.endswith("</fiss>"))

    def test_native_tag_casing_is_asymmetric(self):
        doc = FissDocument.load(sample_path("ExportChapter2.xml"))
        out = doc.serialize()
        self.assertIn("<Date1>", out)   # D majuscule
        self.assertIn("<entry1>", out)  # e minuscule
        self.assertNotIn("<date1>", out)
        self.assertNotIn("<Entry1>", out)


class EscapingTests(unittest.TestCase):
    """Échappement natif : &apos; &quot; &gt; &#x0D;, et &amp; en premier."""

    def test_line_breaks_become_single_cr_entity(self):
        doc = FissDocument(entries=[FissEntry(date="d", text="a\r\nb\nc\rd")])
        out = doc.serialize()
        # Toute forme de saut de ligne -> un unique &#x0D;.
        self.assertIn("a&#x0D;b&#x0D;c&#x0D;d", out)
        self.assertNotIn("\n", out)
        self.assertNotIn("\r", out)

    def test_special_characters_are_escaped_natively(self):
        doc = FissDocument(entries=[FissEntry(date="d", text="""a & b < c > d " e ' f""")])
        out = doc.serialize()
        self.assertIn("&amp;", out)
        self.assertIn("&lt;", out)
        self.assertIn("&gt;", out)
        self.assertIn("&quot;", out)
        self.assertIn("&apos;", out)
        # &amp; échappé en premier : pas de double échappement.
        self.assertNotIn("&amp;amp;", out)

    def test_ampersand_round_trips_without_double_escaping(self):
        original = FissDocument(entries=[FissEntry(date="d", text="R&D <tag> ' \" >")])
        reparsed = FissDocument.parse(original.serialize())
        self.assertEqual(reparsed.entries[0].text, "R&D <tag> ' \" >")


class ToleranceTests(unittest.TestCase):
    """Lecture tolérante : casse legacy et déclaration XML parasite acceptées."""

    def test_lowercase_legacy_tags_are_read(self):
        legacy = (
            "<fiss><Header><Version>1.2</Version><ModName>TakeNotesXML</ModName>"
            "</Header><Data><NumberOfEntries>2</NumberOfEntries>"
            "<date1>Jour</date1><entry1>Texte legacy</entry1></Data></fiss>"
        )
        doc = FissDocument.parse(legacy)
        self.assertEqual(len(doc.entries), 1)
        self.assertEqual(doc.entries[0].date, "Jour")

    def test_write_canonicalizes_legacy_lowercase_to_native(self):
        legacy = (
            "<fiss><Header><Version>1.2</Version><ModName>TakeNotesXML</ModName>"
            "</Header><Data><NumberOfEntries>2</NumberOfEntries>"
            "<date1>Jour</date1><entry1>Texte</entry1></Data></fiss>"
        )
        out = FissDocument.parse(legacy).serialize()
        self.assertIn("<Date1>", out)     # legacy minuscule -> natif majuscule
        self.assertNotIn("<date1>", out)

    def test_xml_declaration_is_tolerated_on_read(self):
        with_decl = (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<fiss><Header><Version>1.2</Version><ModName>TakeNotesXML</ModName>"
            "</Header><Data><NumberOfEntries>1</NumberOfEntries></Data></fiss>"
        )
        doc = FissDocument.parse(with_decl)
        self.assertEqual(doc.entries, [])
        self.assertNotIn("<?xml", doc.serialize())  # jamais réécrit en sortie


class LoudFailureTests(unittest.TestCase):
    """Échec bruyant plutôt que lecture silencieusement fausse."""

    def test_missing_data_section_raises(self):
        broken = "<fiss><Header><Version>1.2</Version><ModName>X</ModName></Header></fiss>"
        with self.assertRaises(FissError):
            FissDocument.parse(broken)

    def test_wrong_root_raises(self):
        with self.assertRaises(FissError):
            FissDocument.parse("<notfiss><Data></Data></notfiss>")

    def test_malformed_xml_raises(self):
        with self.assertRaises(FissError):
            FissDocument.parse("<fiss><Data><entry1>oops")

    def test_gap_in_numbering_raises(self):
        """Trou (entrée 2 manquante mais 3 présente) => corruption détectée."""
        holed = (
            "<fiss><Header><Version>1.2</Version><ModName>X</ModName></Header>"
            "<Data><NumberOfEntries>4</NumberOfEntries>"
            "<Date1>a</Date1><entry1>1</entry1>"
            "<Date3>c</Date3><entry3>3</entry3></Data></fiss>"
        )
        with self.assertRaises(FissError):
            FissDocument.parse(holed)

    def test_orphan_date_without_entry_raises(self):
        orphan = (
            "<fiss><Header><Version>1.2</Version><ModName>X</ModName></Header>"
            "<Data><NumberOfEntries>2</NumberOfEntries>"
            "<Date1>a</Date1></Data></fiss>"
        )
        with self.assertRaises(FissError):
            FissDocument.parse(orphan)


class SaveTests(unittest.TestCase):
    """Écriture native : backup horodaté + garde-fou, sans BOM ni newline parasite."""

    def _tmp(self, name="ExportChapterTest.xml"):
        import tempfile
        directory = tempfile.mkdtemp(prefix="fisstest_")
        return os.path.join(directory, name)

    def test_save_writes_native_bytes_without_bom(self):
        path = self._tmp()
        FissDocument(entries=[FissEntry(date="Jour", text="Texte")]).save(path, backup=False)
        with open(path, "rb") as handle:
            data = handle.read()
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))  # pas de BOM
        self.assertNotIn(b"\r", data)
        self.assertNotIn(b"\n", data)
        self.assertTrue(data.startswith(b"<fiss>"))

    def test_save_creates_timestamped_backup_before_overwrite(self):
        path = self._tmp()
        original = FissDocument(entries=[FissEntry(date="J1", text="v1")])
        self.assertIsNone(original.save(path, backup=True))  # rien à sauvegarder

        updated = FissDocument.load(path)
        updated.entries.append(FissEntry(date="J2", text="v2"))
        backup_path = updated.save(path, backup=True)
        self.assertIsNotNone(backup_path)
        self.assertTrue(os.path.exists(backup_path))
        self.assertIn(".bak", backup_path)
        # Le backup contient la version d'AVANT (1 entrée), le fichier la nouvelle (2).
        self.assertEqual(len(FissDocument.load(backup_path).entries), 1)
        self.assertEqual(len(FissDocument.load(path).entries), 2)

    def test_saved_file_round_trips_through_load(self):
        path = self._tmp()
        doc = FissDocument.load(sample_path("ExportChapter1.xml"))
        doc.save(path, backup=False)
        self.assertEqual(FissDocument.load(path).serialize(), doc.serialize())


if __name__ == "__main__":
    unittest.main()
