"""Adaptateur CLI (transitoire) au-dessus de InjectionService.

Le cœur métier est désormais découplé du terminal (voir InjectionService). Cette
classe ne fait plus QUE de l'interaction console : elle collecte les choix de
l'utilisateur (catégorie, source du texte, arc, date), puis délègue l'exécution au
service, exactement comme le fait l'interface web. Les métadonnées (vestige V1) ne
sont plus demandées.

Les préoccupations purement "fichiers + terminal" (copie du presse-papiers,
archivage des fichiers traités) restent ici, car elles n'ont pas de sens côté web.
"""

import os
import shutil
from datetime import datetime

import pyperclip
from colorama import Fore

from src.EnvLoader import EnvLoader
from src.FileChooser import FileChooser
from src.ShellPrinter import ShellPrinter
from src.Reporter import Reporter
from src.DataExtractor import DataExtractor
from src.InjectionService import InjectionService, InjectionRequest, XML_FILES_MAPPING

# Sous-dossier d'archivage des fichiers traités, commun aux entrées et aux métadonnées.
ARCHIVE_SUBDIR = "_traités"


class TNFCDataInjector:
    """Boucle interactive du CLI. Toute la logique d'injection vit dans le service."""

    def __init__(self):
        self.printer = ShellPrinter()

        env = EnvLoader()
        self.paths = env.get_paths()
        self.entries_dir = self.paths['entries_dir']

        # Reporter avec écho console : les logs du service s'affichent en direct.
        self.reporter = Reporter(echo=True)
        # Le CLI lit un texte brut (presse-papiers ou fichier) : il découpe encore
        # les sections Resume/Text par balises avant de remplir la requête, là où le
        # web dispose désormais de deux champs distincts.
        self.data_extractor = DataExtractor(self.reporter)
        self.service = InjectionService(
            self.paths, pdf_export_file=env.pdf_export_file, reporter=self.reporter
        )

    def choose_category(self):
        self.printer.info("Choisissez une catégorie :")
        categories = self.service.list_categories()
        for i, category in enumerate(categories, start=1):
            self.printer.custom_print(f"{i}. {category}", color=Fore.CYAN)

        choice = self.printer.user_input(f"Choisissez une catégorie (1-{len(categories)}): ")
        try:
            choice_index = int(choice) - 1
            if choice_index < 0 or choice_index >= len(categories):
                raise ValueError
            return categories[choice_index]
        except ValueError:
            self.printer.error("Choix invalide.")
            raise ValueError("Choix invalide.")

    def choose_entry_source(self):
        """True = presse-papiers (défaut), False = fichier existant."""
        self.printer.info("Source du texte enrichi :")
        self.printer.custom_print("1. Utiliser le presse-papiers (par défaut)", color=Fore.CYAN)
        self.printer.custom_print("2. Choisir un fichier existant", color=Fore.CYAN)
        choice = self.printer.user_input("Choix (Entrée = presse-papiers) : ").strip()
        return choice != "2"

    def get_raw_text(self):
        """Renvoie (raw_text, fichier_à_archiver).

        - Presse-papiers : contenu tracé immédiatement dans _traités/, rien à archiver.
        - Fichier : on renvoie son chemin pour archivage après succès.
        """
        if self.choose_entry_source():
            content = pyperclip.paste()
            if not content or not content.strip():
                self.printer.error("Le presse-papiers est vide.")
                raise ValueError("Le presse-papiers est vide.")
            self._save_clipboard_copy(content)
            return content, None

        text_file_path = self._choose_file(self.entries_dir)
        with open(text_file_path, 'r', encoding='utf-8') as f:
            return f.read(), text_file_path

    def choose_arc(self):
        """Menu de sélection d'arc. Entrée -> nouvel arc (renvoie None)."""
        arcs = self.service.list_arcs()
        if not arcs:
            self.printer.info("Aucun arc existant. Un nouvel arc sera créé.")
            return None
        self.printer.info("Choisissez un arc pour l'injection :")
        for i, arc in enumerate(arcs, start=1):
            self.printer.custom_print(f"{i}. {arc}", color=Fore.CYAN)
        choice = self.printer.user_input(
            f"Choisissez un arc (1-{len(arcs)}) ou Entrée pour un nouvel arc : "
        )
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(arcs):
                raise ValueError
            return arcs[idx]
        except (ValueError, IndexError):
            return None  # le service créera un nouvel arc auto-numéroté

    def choose_date(self, category):
        default = self.service.suggest_entry_date(category)
        hint = f" (Entrée = '{default}')" if default else ""
        return self.printer.user_input(
            f"Date de la session pour cette entrée{hint} : "
        ).strip() or default

    def run_injection(self):
        try:
            category = self.choose_category()
            raw_text, entry_file_to_archive = self.get_raw_text()
            arc = self.choose_arc()
            entry_date = self.choose_date(category)

            # Découpage des sections Resume/Text du texte brut (balises), puis envoi
            # des deux champs séparés au service (qui ne parse plus lui-même).
            resume_text, main_text = self.data_extractor.extract_text_sections_from_content(raw_text)

            # Métadonnées abandonnées (vestige V1/ChatGPT) : on n'en demande plus.
            # Le service utilise {} par défaut.
            request = InjectionRequest(
                category=category,
                resume=resume_text,
                text=main_text,
                arc=arc,
                entry_date=entry_date,
            )
            result = self.service.run(request)

            if not result.success:
                self.printer.error("L'injection a échoué. Fichiers non archivés.")
                return

            # Archivage APRÈS succès complet, comme avant.
            self._archive_processed_files(entry_file_to_archive)

        except Exception as e:
            self.printer.error(f"Une erreur s'est produite : {e}")

    # --- Sélection de fichier (menu console, spécifique CLI) ------------------

    def _choose_file(self, dir_path):
        files = FileChooser.list_files(dir_path)
        self.printer.info(f"Fichiers disponibles dans '{dir_path}':")
        for i, name in enumerate(files, start=1):
            self.printer.custom_print(f"{i}. {name}", color=Fore.CYAN)
        choice = self.printer.user_input(f"Choisissez un fichier (1-{len(files)}): ")
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(files):
                raise ValueError
            return os.path.join(dir_path, files[idx])
        except ValueError:
            self.printer.error("Choix invalide.")
            raise ValueError("Choix invalide.")

    # --- Archivage fichiers (spécifique CLI) ---------------------------------

    def _save_clipboard_copy(self, content):
        archive_dir = os.path.join(self.entries_dir, ARCHIVE_SUBDIR)
        os.makedirs(archive_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(archive_dir, f"presse-papiers_{timestamp}.txt")
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(content)
        self.printer.info(f"Texte du presse-papiers sauvegardé : {dest}")

    def _archive_processed_files(self, entry_file_path):
        # Seul le fichier d'entrée est archivé : les métadonnées ne sont plus utilisées.
        if entry_file_path:
            self._move_to_archive(entry_file_path, self.entries_dir)

    def _move_to_archive(self, file_path, base_dir):
        archive_dir = os.path.join(base_dir, ARCHIVE_SUBDIR)
        os.makedirs(archive_dir, exist_ok=True)
        dest = os.path.join(archive_dir, os.path.basename(file_path))
        if os.path.exists(dest):
            base, ext = os.path.splitext(os.path.basename(file_path))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(archive_dir, f"{base}_{timestamp}{ext}")
        shutil.move(file_path, dest)
        self.printer.info(f"Fichier archivé : {os.path.basename(file_path)} -> {archive_dir}")
