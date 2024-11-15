import os

from src.DataExtractor import DataExtractor
from src.EnvLoader import EnvLoader
from src.FileChooser import FileChooser
from src.JSONInjector import JSONInjector
from src.XMLInjector import XMLInjector
from src.ShellPrinter import ShellPrinter  # Import the ShellPrinter class
from src.PDFExtractor import PDFGenerator
from colorama import Fore


class TNFCDataInjector:
    """
    Main class that orchestrates all operations related to file handling and data injection.
    """
    def __init__(self):
        # Initialize the printer for output
        self.printer = ShellPrinter()

        # Load environment variables
        env_loader = EnvLoader()
        paths = env_loader.get_paths()

        # Instantiate other classes
        self.file_chooser = FileChooser()
        self.data_extractor = DataExtractor()
        self.xml_injector = XMLInjector(paths['take_notes_export_dir'])
        self.json_injector = JSONInjector(paths['full_context_json_path'])

        self.entries_dir = paths['entries_dir']
        self.metadatas_dir = paths['metadatas_dir']

        # Mapping of categories to XML files
        self.xml_files_mapping = {
            'journal': 'ExportChapter1.xml',
            'bestiaire': 'ExportChapter2.xml',
            'quetes': 'ExportChapter3.xml',
            'personnages': 'ExportChapter4.xml',
            'divers': 'ExportChapter5.xml'
        }

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
            xml_file_path = os.path.join(self.xml_injector.export_dir, xml_file_name)

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

            self.printer.info("Génération du PDF.")

            try:
                pdf_output_path = os.getenv("PDF_OUTPUT_PATH", "output/Journal_Entries_By_Date.pdf")
                pdf_generator = PDFGenerator(xml_file_path, pdf_output_path)
                pdf_generator.run()
            except Exception as e:
                self.printer.error(f"Problème lors de la génération du PDF : {e}")


        except Exception as e:
            self.printer.error(f"Une erreur s'est produite : {e}")

