"""Orchestrateur du pipeline d'injection, sans aucune interaction terminal.

Remplace l'ancien `TNFCDataInjector.run_injection` qui posait des questions au
milieu du traitement. Ici, toutes les décisions (catégorie, arc, date, métadonnées,
texte) arrivent en une fois via `InjectionRequest`, et le résultat — y compris le
journal d'exécution — est renvoyé dans `InjectionResult`.

C'est le point d'entrée unique appelé aussi bien par l'interface web que par un
éventuel adaptateur CLI : le cœur métier ne connaît plus l'origine des données.

Invariant préservé : le JSON n'est sauvegardé sur disque qu'APRÈS le succès de
l'injection XML, pour que les deux fichiers ne divergent jamais.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from src.Reporter import Reporter
from src.JSONInjector import JSONInjector
from src.XMLInjector import XMLInjector
from src.PDFExtractor import PDFGenerator
from src.EnvLoader import EnvLoader
from src.Database import InjectionDatabase, compute_text_hash


# Correspondance catégorie -> fichier XML TakeNotes (déplacée hors du CLI).
XML_FILES_MAPPING = {
    'journal': 'ExportChapter1.xml',
    'bestiaire': 'ExportChapter2.xml',
    'quetes': 'ExportChapter3.xml',
    'personnages': 'ExportChapter4.xml',
    'divers': 'ExportChapter5.xml',
}


@dataclass
class InjectionRequest:
    """Tous les paramètres d'une injection, collectés en amont (formulaire web).

    Le résumé et le texte arrivent désormais dans deux champs distincts : plus
    besoin de balises `Resume :` / `Text :` dans un texte unique. Le CLI, qui lit
    un texte brut, réalise le découpage en amont (voir `DataExtractor`) avant de
    remplir cette requête.
    """
    category: str                       # clé de XML_FILES_MAPPING
    resume: str = ""                    # résumé de l'entrée (optionnel)
    text: str = ""                     # corps du journal (obligatoire)
    metadata: dict = field(default_factory=dict)
    arc: Optional[str] = None           # arc cible ; None/"" -> nouvel arc auto
    entry_date: Optional[str] = None    # date calendrier de jeu ; "" -> dernière connue
    max_tokens: Optional[int] = None    # largeur de segmentation XML ; None -> env
    generate_pdf: bool = True
    allow_duplicate: bool = False       # True -> force l'injection malgré un doublon


@dataclass
class InjectionResult:
    success: bool
    messages: list                      # journal d'exécution (voir Reporter)
    entry_number: Optional[int] = None
    arc: Optional[str] = None
    category: Optional[str] = None
    xml_file: Optional[str] = None
    pdf_path: Optional[str] = None
    injection_id: Optional[int] = None  # id de la ligne d'archive (BDD)
    duplicate: Optional[dict] = None    # injection existante si doublon détecté


class InjectionService:
    def __init__(self, paths, pdf_output_path=None, pdf_export_file=None,
                 reporter=None, db=None):
        """
        :param paths: dict avec full_context_json_path, take_notes_export_dir
                      (mêmes clés que EnvLoader.get_paths()).
        :param db: InjectionDatabase pour l'archivage/anti-doublon. None -> pas
                   d'archivage (utile pour tests isolés).
        """
        self.reporter = reporter or Reporter()
        self.paths = paths
        self.pdf_output_path = pdf_output_path or os.getenv(
            "PDF_OUTPUT_PATH", "output/Journal_Entries_By_Date.pdf"
        )
        self.pdf_export_file = pdf_export_file or os.getenv("PDF_EXPORT_FILE")
        self.db = db

        self.json_injector = JSONInjector(paths['full_context_json_path'], self.reporter)
        self.xml_injector = XMLInjector(paths['take_notes_export_dir'], self.reporter)

    @classmethod
    def from_env(cls, reporter=None, db=None):
        """Construit le service à partir du .env (valide les chemins au passage).

        Par défaut, branche une InjectionDatabase (archivage activé). Passer db
        explicitement pour surcharger l'emplacement de la base.
        """
        env = EnvLoader()
        return cls(
            paths=env.get_paths(),
            pdf_export_file=env.pdf_export_file,
            reporter=reporter,
            db=db if db is not None else InjectionDatabase(),
        )

    # --- Helpers de lecture pour alimenter l'UI (aucune écriture) -------------

    def list_categories(self):
        return list(XML_FILES_MAPPING.keys())

    def list_arcs(self):
        """Arcs existants dans le JSON de contexte (pour le menu déroulant web)."""
        data = self.json_injector.load_full_context_json()
        return JSONInjector.list_arcs(data)

    def suggest_entry_date(self, category):
        """Dernière date connue de la catégorie, proposée par défaut dans le form."""
        xml_file_name = XML_FILES_MAPPING.get(category)
        if not xml_file_name:
            return ""
        return self.xml_injector.get_last_date(xml_file_name)

    # --- Pipeline complet ----------------------------------------------------

    def run(self, request: InjectionRequest) -> InjectionResult:
        """Exécute JSON -> XML -> PDF et renvoie un résultat structuré.

        Aucune exception ne remonte : les erreurs sont consignées dans le reporter
        et reflétées par `success=False`, pour que la couche web réponde proprement.
        """
        try:
            xml_file_name = XML_FILES_MAPPING.get(request.category)
            if not xml_file_name:
                self.reporter.error(f"Catégorie inconnue : {request.category}")
                return self._fail(request.category)

            xml_file_path = os.path.join(self.xml_injector.export_dir, xml_file_name)

            # 1. Résumé et texte arrivent déjà séparés (deux champs) : aucun parsing
            # par balises. Le résumé est optionnel ; le texte principal est requis.
            resume_text = (request.resume or "").strip()
            main_text = (request.text or "").strip()
            if not resume_text:
                self.reporter.warning("Aucun résumé fourni : le résumé sera vide.")
            if not main_text:
                self.reporter.error("Le texte principal est vide.")
                return self._fail(request.category, xml_file_name)

            # 1bis. Détection de doublon (avant toute écriture). Le hash porte sur le
            # texte injecté : un texte déjà traité est signalé, à moins que l'appelant
            # ne force explicitement (allow_duplicate) après confirmation côté UI.
            text_hash = compute_text_hash(main_text)
            if self.db is not None and not request.allow_duplicate:
                existing = self.db.find_duplicate(text_hash)
                if existing:
                    self.reporter.error(
                        "Ce texte a déjà été injecté le "
                        f"{existing.get('date_injection')} "
                        f"(catégorie « {existing.get('categorie')} », "
                        f"arc « {existing.get('arc')} », entrée #{existing.get('entry_number')})."
                    )
                    self.reporter.info(
                        "Aucune écriture effectuée. Relancez avec « forcer » pour injecter malgré tout."
                    )
                    result = self._fail(request.category, xml_file_name)
                    result.duplicate = existing
                    return result

            # 2. Charger le JSON de contexte et injecter l'entrée EN MÉMOIRE.
            full_context_data = self.json_injector.load_full_context_json()
            entry_number, selected_arc = self.json_injector.inject_entry_in_json(
                resume_text, main_text, request.metadata, full_context_data, request.arc
            )

            # 3. Injecter dans le XML AVANT de persister le JSON (invariant de synchro).
            try:
                self.xml_injector.inject_text_in_xml(
                    main_text, xml_file_name, request.entry_date, request.max_tokens
                )
            except Exception as e:
                self.reporter.error(f"Erreur lors de l'injection dans le XML : {e}")
                self.reporter.error(
                    "Le JSON n'a pas été sauvegardé afin de rester synchronisé avec le XML."
                )
                return self._fail(request.category, xml_file_name)

            # 4. Les deux injections ont réussi : on persiste le JSON sur disque.
            self.json_injector.save_full_context_json(full_context_data)
            self.reporter.success("Le processus d'injection a été terminé avec succès.")

            # 5. PDF (optionnel, non bloquant).
            pdf_path = None
            if request.generate_pdf:
                self.reporter.info("Génération du PDF.")
                try:
                    pdf_generator = PDFGenerator(
                        xml_file_path, self.pdf_output_path,
                        pdf_export_file=self.pdf_export_file, reporter=self.reporter,
                    )
                    pdf_path = pdf_generator.run()
                except Exception as e:
                    self.reporter.error(f"Problème lors de la génération du PDF : {e}")

            # 6. Archivage durable en base (après succès complet). Non bloquant :
            # une injection réussie ne doit pas être annulée par un souci d'archive.
            injection_id = None
            if self.db is not None:
                try:
                    injection_id = self.db.record_injection(
                        categorie=request.category, arc=selected_arc,
                        entry_number=entry_number, date_session=request.entry_date,
                        resume=resume_text, texte=main_text, metadata=request.metadata,
                        xml_file=xml_file_name, pdf_path=pdf_path, text_hash=text_hash,
                    )
                    self.reporter.success(f"Injection archivée en base (id {injection_id}).")
                except Exception as e:
                    self.reporter.warning(f"Injection réussie mais archivage BDD échoué : {e}")

            return InjectionResult(
                success=True,
                messages=self.reporter.messages,
                entry_number=entry_number,
                arc=selected_arc,
                category=request.category,
                xml_file=xml_file_name,
                pdf_path=pdf_path,
                injection_id=injection_id,
            )

        except Exception as e:
            self.reporter.error(f"Une erreur s'est produite : {e}")
            return self._fail(request.category)

    def _fail(self, category=None, xml_file=None):
        return InjectionResult(
            success=False,
            messages=self.reporter.messages,
            category=category,
            xml_file=xml_file,
        )
