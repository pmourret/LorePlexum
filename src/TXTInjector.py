import os
from src.ShellPrinter import ShellPrinter
from src.FileChooser import FileChooser


class TXTInjector:
    """
    Handles the injection of metadata from a selected .txt file directly into full_context.txt.
    """

    def __init__(self, full_context_txt_path, metadatas_dir):
        self.full_context_txt_path = full_context_txt_path
        self.metadatas_dir = metadatas_dir
        self.file_chooser = FileChooser()
        self.printer = ShellPrinter()

    def get_next_entry_number(self):
        """
        Determines the next entry number by counting existing entries in full_context.txt.
        """
        entry_count = 0
        try:
            with open(self.full_context_txt_path, 'r', encoding='utf-8') as file:
                for line in file:
                    if line.startswith("EntryNumber :"):
                        entry_count += 1
        except FileNotFoundError:
            self.printer.info("Le fichier full_context.txt n'existe pas encore. Création d'un nouveau fichier.")
        return entry_count + 1

    def inject_metadata_file(self):
        """
        Prompts the user to select a metadata file and injects its content into full_context.txt.
        """
        # Demande à l'utilisateur de sélectionner le fichier de métadonnées
        metadata_file_path = self.file_chooser.choose_file_from_dir(self.metadatas_dir)
        if not metadata_file_path:
            self.printer.error("Aucun fichier de métadonnées sélectionné.")
            return

        # Lit le contenu brut du fichier de métadonnées
        try:
            with open(metadata_file_path, 'r', encoding='utf-8') as metadata_file:
                metadata_content = metadata_file.read()
        except FileNotFoundError:
            self.printer.error(f"Le fichier {metadata_file_path} n'a pas pu être trouvé.")
            return

        # Crée une nouvelle entrée avec un EntryNumber et injecte le contenu brut des métadonnées
        entry_number = self.get_next_entry_number()
        formatted_entry = f"""
******************************

EntryNumber : {entry_number}
{metadata_content}

******************************
"""
        # Écrit la nouvelle entrée dans full_context.txt
        with open(self.full_context_txt_path, 'a', encoding='utf-8') as full_context_file:
            full_context_file.write(formatted_entry)

        self.printer.success(
            f"Le fichier de métadonnées '{os.path.basename(metadata_file_path)}' a été injecté avec succès sous EntryNumber {entry_number}.")
