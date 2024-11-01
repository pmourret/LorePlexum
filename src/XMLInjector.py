import os
import xml.etree.ElementTree as ET
import re
import textwrap

class XMLInjector:
    """
    Handles injection of data into XML files.
    """

    def __init__(self, export_dir):
        self.export_dir = export_dir

    def inject_text_in_xml(self, input_text, xml_file_name):
        if not input_text:
            raise ValueError("Le texte d'entrée est vide ou None.")

        # Normalisation et vérification du chemin du fichier
        xml_file_path = os.path.normpath(os.path.join(self.export_dir, xml_file_name))
        if not os.path.exists(xml_file_path):
            raise FileNotFoundError(f"Le fichier XML {xml_file_path} n'existe pas.")

        # Chargement et parsing du fichier XML
        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        # Navigation vers la section <Data> où les entrées doivent être ajoutées
        data_section = root.find('Data')
        if data_section is None:
            raise ValueError("La section <Data> est manquante dans le fichier XML.")

        # Division du texte d'entrée en segments sans couper les mots
        max_tokens = int(os.getenv("MAX_TOKENS_PER_ENTRY", 500))
        input_text_segments = textwrap.wrap(input_text, width=max_tokens, break_long_words=False, replace_whitespace=False)

        # Extraction du numéro d'entrée courant (en tenant compte des dates et des entrées existantes)
        existing_entry_numbers = sorted([
            int(re.search(r'\d+', elem.tag).group(0))
            for elem in data_section if re.match(r'(date|entry)\d+', elem.tag)
        ])

        # Assurer une numérotation séquentielle pour les nouvelles entrées
        if existing_entry_numbers:
            current_entry_number = existing_entry_numbers[-1]
        else:
            current_entry_number = 0

        # Récupération de la dernière date existante
        last_date_element = data_section.find(f'date{current_entry_number}')
        last_date_text = last_date_element.text if last_date_element is not None else "DateAutomatique"

        # Injection des textes segmentés dans les entrées existantes ou nouvelles
        todo_found = False
        segments_processed = 0

        for i in range(1, current_entry_number + 1):
            entry_text = data_section.find(f'entry{i}')
            if entry_text is not None and "todo" in entry_text.text.lower() and segments_processed < len(input_text_segments):
                entry_text.text = input_text_segments[segments_processed]
                print(f"L'entrée TODO (entry{i}) a été remplacée par le texte complet.")
                todo_found = True
                segments_processed += 1

        # Ajouter la première partie si aucun TODO n'a été trouvé
        while segments_processed < len(input_text_segments):
            current_entry_number += 1
            new_date = ET.SubElement(data_section, f'date{current_entry_number}')
            new_date.text = last_date_text  # Utiliser la dernière date connue
            new_entry = ET.SubElement(data_section, f'entry{current_entry_number}')
            new_entry.text = input_text_segments[segments_processed]
            print(f"Nouvelle entrée XML ajoutée avec ID {current_entry_number}.")
            segments_processed += 1

        # Mettre à jour la balise <NumberOfEntries> dans la section <Data>
        self.update_number_of_entries(data_section)

        # Sauvegarde des changements dans le fichier XML
        tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
        print("L'injection dans le XML a été réalisée avec succès.")

    def update_number_of_entries(self, data_section):
        """Update the <NumberOfEntries> in the <Data> section."""
        number_of_entries = len([elem for elem in data_section if re.match(r'entry\d+', elem.tag)])
        number_of_entries_element = data_section.find('NumberOfEntries')
        if number_of_entries_element is not None:
            number_of_entries_element.text = str(number_of_entries)
        else:
            # Si <NumberOfEntries> n'existe pas, l'ajouter à <Data>
            number_of_entries_element = ET.SubElement(data_section, 'NumberOfEntries')
            number_of_entries_element.text = str(number_of_entries)

