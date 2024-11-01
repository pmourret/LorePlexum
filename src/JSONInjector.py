import os
import json


class JSONInjector:
    """
    Handles injection of journal entries into JSON files.
    """

    def __init__(self, full_context_json_path):
        self.full_context_json_path = full_context_json_path

    def load_full_context_json(self):
        if not os.path.exists(self.full_context_json_path):
            raise FileNotFoundError(f"Le fichier JSON {self.full_context_json_path} n'existe pas.")

        with open(self.full_context_json_path, 'r', encoding='utf-8') as json_file:
            try:
                data = json.load(json_file)
                print("Données JSON principales chargées avec succès.")
                return data
            except json.JSONDecodeError:
                raise ValueError("Erreur lors du chargement des données JSON principales.")

    def load_metadata_json(self, metadata_file_path):
        """
        Loads metadata JSON from the given file path.

        :param metadata_file_path: The file path to the JSON metadata file.
        :return: A dictionary containing the loaded JSON metadata.
        """
        if not os.path.exists(metadata_file_path):
            raise FileNotFoundError(f"Le fichier JSON de métadonnées {metadata_file_path} n'existe pas.")

        with open(metadata_file_path, 'r', encoding='utf-8') as file:
            try:
                metadata = json.load(file)
                print("Données de métadonnées JSON chargées avec succès.")
                return metadata
            except json.JSONDecodeError:
                raise ValueError("Erreur lors du chargement des métadonnées JSON.")

    def inject_entry_in_json(self, resume_text, main_text, metadata, json_data):
        # Ensure the character_arc structure and choose the arc
        character_arc = json_data.setdefault("character_arc", {})
        selected_arc = self.choose_arc(character_arc)

        # Access the existing journals array within the selected arc
        arc_data = character_arc[selected_arc]
        journals = arc_data.setdefault("journals", [])

        # Create the new entry
        entry_number = len(journals) + 1
        new_entry = {
            "entry_number": entry_number,
            "summary": resume_text,
            "text": main_text,
            "metadata": metadata
        }

        # Append the new entry to the existing journals array
        journals.append(new_entry)
        print(f"Nouvelle entrée ajoutée au journal avec entry_number {entry_number}.")

    def choose_arc(self, character_arc):
        arc_keys = list(character_arc.keys())

        if not arc_keys:
            print("Aucun arc trouvé. Création d'un nouvel arc par défaut : arc_1.")
            return "arc_1"

        print("Choisissez un arc pour l'injection :")
        for i, arc in enumerate(arc_keys, start=1):
            print(f"{i}. {arc}")

        choice = input(f"Choisissez un arc (1-{len(arc_keys)}) ou appuyez sur Entrée pour créer un nouvel arc: ")
        try:
            choice_index = int(choice) - 1
            if choice_index < 0 or choice_index >= len(arc_keys):
                raise ValueError
            return arc_keys[choice_index]
        except (ValueError, IndexError):
            new_arc_number = len(arc_keys) + 1
            new_arc = f"arc_{new_arc_number}"
            character_arc[new_arc] = {}
            print(f"Nouvel arc créé : {new_arc}")
            return new_arc

    def save_full_context_json(self, json_data):
        with open(self.full_context_json_path, 'w', encoding='utf-8') as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        print("Données JSON principales sauvegardées avec succès.")
