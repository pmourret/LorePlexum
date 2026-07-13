import os
import xml.etree.ElementTree as ET
import re
import textwrap

from src.Reporter import Reporter


class XMLInjector:
    """
    Handles injection of data into XML files.
    """

    def __init__(self, export_dir, reporter=None):
        self.export_dir = export_dir
        self.reporter = reporter or Reporter()

    def _resolve_xml_path(self, xml_file_name):
        """Normalise et valide le chemin du fichier XML de la catégorie."""
        xml_file_path = os.path.normpath(os.path.join(self.export_dir, xml_file_name))
        if not os.path.exists(xml_file_path):
            self.reporter.error(f"Le fichier XML {xml_file_path} n'existe pas.")
            raise FileNotFoundError(f"Le fichier XML {xml_file_path} n'existe pas.")
        return xml_file_path

    @staticmethod
    def _existing_entry_numbers(data_section):
        return sorted([
            int(re.search(r'\d+', elem.tag).group(0))
            for elem in data_section if re.match(r'(date|entry)\d+', elem.tag)
        ])

    def get_last_date(self, xml_file_name):
        """Retourne la dernière date connue du XML (défaut proposé par l'UI).

        Extrait la logique qui, auparavant, était mêlée au prompt interactif : le web
        s'en sert pour pré-remplir le champ « date de session » sans rien injecter.
        Renvoie "" si le fichier n'existe pas / n'a pas d'entrée datée.
        """
        try:
            xml_file_path = self._resolve_xml_path(xml_file_name)
            tree = ET.parse(xml_file_path)
        except (FileNotFoundError, ET.ParseError):
            return ""
        data_section = tree.getroot().find('Data')
        if data_section is None:
            return ""
        numbers = self._existing_entry_numbers(data_section)
        if not numbers:
            return ""
        last_date_element = data_section.find(f'date{numbers[-1]}')
        return last_date_element.text if last_date_element is not None else ""

    def inject_text_in_xml(self, input_text, xml_file_name, entry_date=None, max_tokens=None):
        """Injecte le texte dans le XML de la catégorie.

        `entry_date` (date du calendrier de jeu) et `max_tokens` sont désormais des
        paramètres explicites : la saisie interactive a disparu du cœur métier. Si
        `entry_date` est vide, on retombe sur la dernière date connue puis, à défaut,
        sur "DateAutomatique".
        """
        if not input_text:
            self.reporter.error("Le texte d'entrée est vide ou None.")
            raise ValueError("Le texte d'entrée est vide ou None.")

        xml_file_path = self._resolve_xml_path(xml_file_name)

        # Chargement et parsing du fichier XML
        try:
            tree = ET.parse(xml_file_path)
        except ET.ParseError as e:
            self.reporter.error(f"Erreur lors du parsing du fichier XML : {e}")
            raise ValueError(f"Erreur lors du parsing du fichier XML : {e}")
        root = tree.getroot()

        # Navigation vers la section <Data> où les entrées doivent être ajoutées
        data_section = root.find('Data')
        if data_section is None:
            self.reporter.error("La section <Data> est manquante dans le fichier XML.")
            raise ValueError("La section <Data> est manquante dans le fichier XML.")

        # Division du texte d'entrée en segments sans couper les mots
        if max_tokens is None:
            max_tokens = int(os.getenv("MAX_TOKENS_PER_ENTRY", 500))
        input_text_segments = textwrap.wrap(input_text, width=max_tokens, break_long_words=False, replace_whitespace=False)

        # Extraction du numéro d'entrée courant (dates et entrées existantes)
        existing_entry_numbers = self._existing_entry_numbers(data_section)
        current_entry_number = existing_entry_numbers[-1] if existing_entry_numbers else 0

        # Date réelle de la session. Fournie par l'appelant (formulaire web ou CLI).
        # Fallback : dernière date connue, puis "DateAutomatique".
        entry_date = (entry_date or "").strip()
        if not entry_date:
            last_date_element = data_section.find(f'date{current_entry_number}')
            entry_date = last_date_element.text if last_date_element is not None else ""
        if not entry_date:
            entry_date = "DateAutomatique"

        # Injection des textes segmentés dans les entrées existantes ou nouvelles
        segments_processed = 0

        for i in range(1, current_entry_number + 1):
            entry_text = data_section.find(f'entry{i}')
            if entry_text is not None and "todo" in entry_text.text.lower() and segments_processed < len(input_text_segments):
                entry_text.text = input_text_segments[segments_processed]
                self.reporter.success(f"L'entrée TODO (entry{i}) a été remplacée par le texte complet.")
                segments_processed += 1

        # Ajouter les segments restants comme nouvelles entrées
        while segments_processed < len(input_text_segments):
            current_entry_number += 1
            new_date = ET.SubElement(data_section, f'date{current_entry_number}')
            new_date.text = entry_date  # Date réelle fournie par l'appelant
            new_entry = ET.SubElement(data_section, f'entry{current_entry_number}')
            new_entry.text = input_text_segments[segments_processed]
            self.reporter.info(f"Nouvelle entrée XML ajoutée avec ID {current_entry_number}.")
            segments_processed += 1

        # Mettre à jour la balise <NumberOfEntries> dans la section <Data>
        self.update_number_of_entries(data_section)

        # Sauvegarde des changements dans le fichier XML
        try:
            tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
            self.reporter.success("L'injection dans le XML a été réalisée avec succès.")
        except ET.ParseError as e:
            self.reporter.error(f"Erreur lors de l'écriture du fichier XML : {e}")
            raise ValueError(f"Erreur lors de l'écriture du fichier XML : {e}")

    def update_number_of_entries(self, data_section):
        """Update the <NumberOfEntries> in the <Data> section."""
        number_of_entries = len([elem for elem in data_section if re.match(r'entry\d+', elem.tag)])
        number_of_entries_element = data_section.find('NumberOfEntries')
        if number_of_entries_element is not None:
            number_of_entries_element.text = str(number_of_entries + 1)
            self.reporter.info(f"Mise à jour de <NumberOfEntries> à {number_of_entries}.")
        else:
            # Si <NumberOfEntries> n'existe pas, l'ajouter à <Data>
            number_of_entries_element = ET.SubElement(data_section, 'NumberOfEntries')
            number_of_entries_element.text = str(number_of_entries)
            self.reporter.info(f"Ajout de la balise <NumberOfEntries> avec la valeur {number_of_entries}.")
