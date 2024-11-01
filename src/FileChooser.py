import os
from src.ShellPrinter import ShellPrinter  # Import the ShellPrinter class
from colorama import Fore

class FileChooser:
    """
    Handles file selection from a given directory.
    """
    def __init__(self):
        self.printer = ShellPrinter()

    def choose_file_from_dir(self, dir_path):
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        if not files:
            self.printer.error(f"Aucun fichier trouvé dans le répertoire '{dir_path}'.")
            raise FileNotFoundError(f"Aucun fichier trouvé dans le répertoire '{dir_path}'.")

        self.printer.info(f"Fichiers disponibles dans '{dir_path}':")
        for i, file_name in enumerate(files, start=1):
            self.printer.custom_print(f"{i}. {file_name}", color=Fore.CYAN)

        choice = self.printer.user_input(f"Choisissez un fichier à importer (1-{len(files)}): ")
        try:
            choice_index = int(choice) - 1
            if choice_index < 0 or choice_index >= len(files):
                self.printer.error("Choix invalide.")
                raise ValueError("Choix invalide.")
            return os.path.join(dir_path, files[choice_index])
        except ValueError:
            self.printer.error("Choix invalide.")
            raise ValueError("Choix invalide.")
