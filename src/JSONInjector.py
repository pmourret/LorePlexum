import os
import json

from src.Reporter import Reporter


class JSONInjector:
    """
    Handles injection of journal entries into JSON files.
    """

    def __init__(self, full_context_json_path, reporter=None):
        self.full_context_json_path = full_context_json_path
        self.reporter = reporter or Reporter()

    def load_full_context_json(self):
        if not os.path.exists(self.full_context_json_path):
            self.reporter.error(f"Le fichier JSON {self.full_context_json_path} n'existe pas.")
            raise FileNotFoundError(f"Le fichier JSON {self.full_context_json_path} n'existe pas.")

        with open(self.full_context_json_path, 'r', encoding='utf-8') as json_file:
            try:
                data = json.load(json_file)
                self.reporter.success("Données JSON principales chargées avec succès.")
                return data
            except json.JSONDecodeError:
                self.reporter.error("Erreur lors du chargement des données JSON principales.")
                raise ValueError("Erreur lors du chargement des données JSON principales.")

    def load_metadata_json(self, metadata_file_path):
        """
        Loads metadata JSON from the given file path.

        :param metadata_file_path: The file path to the JSON metadata file.
        :return: A dictionary containing the loaded JSON metadata.
        """
        if not os.path.exists(metadata_file_path):
            self.reporter.error(f"Le fichier JSON de métadonnées {metadata_file_path} n'existe pas.")
            raise FileNotFoundError(f"Le fichier JSON de métadonnées {metadata_file_path} n'existe pas.")

        with open(metadata_file_path, 'r', encoding='utf-8') as file:
            try:
                metadata = json.load(file)
                self.reporter.success("Données de métadonnées JSON chargées avec succès.")
                return metadata
            except json.JSONDecodeError:
                self.reporter.error("Erreur lors du chargement des métadonnées JSON.")
                raise ValueError("Erreur lors du chargement des métadonnées JSON.")

    @staticmethod
    def list_arcs(json_data):
        """Retourne la liste des arcs existants (pour alimenter le formulaire web).

        Lecture seule : ne modifie pas la structure. Utilisée par l'UI pour proposer
        les arcs disponibles avant l'injection.
        """
        character_arc = json_data.get("character_arc", {}) if json_data else {}
        return list(character_arc.keys())

    def resolve_arc(self, character_arc, arc):
        """Détermine l'arc cible à partir du choix passé en paramètre.

        Remplace l'ancien menu interactif `choose_arc` :
          - arc vide/None      -> création d'un nouvel arc auto-numéroté (arc_{n+1}) ;
          - arc = clé existante -> réutilisation de cet arc ;
          - arc = nom inédit    -> création d'un arc portant ce nom.
        """
        arc_keys = list(character_arc.keys())

        if not arc:
            new_arc = f"arc_{len(arc_keys) + 1}"
            character_arc.setdefault(new_arc, {})
            self.reporter.info(f"Nouvel arc créé : {new_arc}")
            return new_arc

        if arc in character_arc:
            self.reporter.info(f"Injection dans l'arc existant : {arc}")
            return arc

        character_arc.setdefault(arc, {})
        self.reporter.info(f"Nouvel arc créé : {arc}")
        return arc

    def inject_entry_in_json(self, resume_text, main_text, metadata, json_data, arc=None):
        """Injecte une entrée dans l'arc choisi. Retourne le numéro d'entrée créé.

        `arc` est désormais un paramètre explicite (voir resolve_arc) au lieu d'une
        saisie interactive, afin que le pipeline soit pilotable par le web comme par
        le CLI.
        """
        # Ensure the character_arc structure and resolve the target arc
        character_arc = json_data.setdefault("character_arc", {})
        selected_arc = self.resolve_arc(character_arc, arc)

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
        self.reporter.success(f"Nouvelle entrée ajoutée au journal avec entry_number {entry_number}.")
        return entry_number, selected_arc

    def save_full_context_json(self, json_data):
        with open(self.full_context_json_path, 'w', encoding='utf-8') as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        self.reporter.success("Données JSON principales sauvegardées avec succès.")
