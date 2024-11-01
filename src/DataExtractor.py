import re
from src.ShellPrinter import ShellPrinter  # Import the ShellPrinter class
from colorama import Fore

class DataExtractor:
    """
    Extracts sections of text from a given file.
    """
    def __init__(self):
        self.printer = ShellPrinter()

    def extract_text_sections(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                resume_match = re.search(r'Resume :\s*(.*?)(?:\n{2,}|$)', content, re.DOTALL)
                text_match = re.search(r'Text :\s*(.*?)(?:\n{2,}|$)', content, re.DOTALL)

                resume_text = resume_match.group(1).strip() if resume_match else ""
                main_text = text_match.group(1).strip() if text_match else ""

                if not main_text:
                    self.printer.error("Texte après 'Text:' non trouvé dans le fichier.")
                    raise ValueError("Texte après 'Text:' non trouvé dans le fichier.")

                self.printer.success("Extraction des sections de texte réussie.")
                return resume_text, main_text

        except FileNotFoundError:
            self.printer.error(f"Le fichier {file_path} n'existe pas.")
            raise
        except Exception as e:
            self.printer.error(f"Erreur lors de l'extraction des sections de texte : {e}")
            raise
