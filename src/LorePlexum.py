from src.DataExtractor import DataExtractor
from src.EnvLoader import EnvLoader
from src.FileChooser import FileChooser
from src.JSONInjector import JSONInjector
from src.XMLInjector import XMLInjector
from src.ShellPrinter import ShellPrinter  # Import the ShellPrinter class
from colorama import Fore


class TNFCDataInjector:
    """
    Main class that orchestrates all operations related to file handling and data injection.
    """

    def __init__(self):
        # Initialisation du gestionnaire de messages
        self.printer = ShellPrinter()

        # Chargement des chemins et du format d'injection depuis l'environnement
        env_loader = EnvLoader()
        paths_and_format = env_loader.get_paths_and_format()

        # Initialisation des chemins de répertoires
        self.entries_dir = paths_and_format['entries_dir']
        self.metadatas_dir = paths_and_format['metadatas_dir']

        # Choix de l'injecteur basé sur le format spécifié (JSON ou TXT)
        self.injection_format = paths_and_format['injection_format']
        if self.injection_format == 'JSON':
            self.injector = JSONInjector(paths_and_format['full_context_json_path'])
            self.printer.info("Mode d'injection : JSON")
        else:
            self.injector = TXTInjector(paths_and_format['full_context_txt_path'], self.metadatas_dir)
            self.printer.info("Mode d'injection : TXT")

        # Initialisation du sélecteur de fichiers et de l'extracteur de données
        self.file_chooser = FileChooser()
        self.data_extractor = DataExtractor()

    def choose_category(self):
        """
        Prompts the user to choose a category from a list and returns the corresponding XML file mapping.
        """
        self.printer.info("Choisissez une catégorie :")
        categories = list(self.xml_files_mapping.keys())
        for i, category in enumerate(categories, start=1):
            self.printer.custom_print(f"{i}. {category}", color=Fore.CYAN)

        choice = self.printer.user_input(f"Choisissez une catégorie (1-{len(categories)}): ")
        try:
            choice_index = int(choice) - 1
            if choice_index < 0 or choice_index >= len(categories):
                raise ValueError
            selected_category = categories[choice_index]
            return self.xml_files_mapping[selected_category]
        except ValueError:
            self.printer.error("Choix invalide.")
            raise ValueError("Choix invalide.")

    def run_injection(self):
        """Main method to run the injection process."""
        try:
            # Choisir une catégorie et obtenir le nom du fichier XML associé
            xml_file_name = self.choose_category()

            # Choisir un fichier texte et en extraire les sections
            text_file_path = self.file_chooser.choose_file_from_dir(self.entries_dir)
            resume_text, main_text = self.data_extractor.extract_text_sections(text_file_path)

            # Charger les données JSON complètes
            full_context_data = self.json_injector.load_full_context_json()

            # Choisir un fichier de métadonnées et le charger
            metadata_file_path = self.file_chooser.choose_file_from_dir(self.metadatas_dir)
            metadata = self.json_injector.load_metadata_json(metadata_file_path)

            # Injecter l'entrée dans le fichier JSON
            self.json_injector.inject_entry_in_json(resume_text, main_text, metadata, full_context_data)

            # Sauvegarder les changements dans le JSON
            self.json_injector.save_full_context_json(full_context_data)

            # Injecter le texte dans le fichier XML correspondant
            try:
                self.xml_injector.inject_text_in_xml(main_text, xml_file_name)
            except ValueError as e:
                self.printer.error(f"Erreur lors de l'injection dans le XML : {e}")
                return

            self.printer.success("Le processus d'injection a été terminé avec succès.")

        except Exception as e:
            self.printer.error(f"Une erreur s'est produite : {e}")


    def inject_txt(self):
        """
        Injection process specifically for TXT format.
        """
        # Injection directe dans full_context.txt en sélectionnant le fichier de métadonnées
        self.injector.inject_metadata_file()