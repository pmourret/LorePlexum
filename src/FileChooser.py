import os

class FileChooser:
    """
    Handles file selection from a given directory.
    """
    @staticmethod
    def choose_file_from_dir(dir_path):
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        if not files:
            raise FileNotFoundError(f"Aucun fichier trouvé dans le répertoire '{dir_path}'.")

        print(f"Fichiers disponibles dans '{dir_path}':")
        for i, file_name in enumerate(files, start=1):
            print(f"{i}. {file_name}")

        choice = input(f"Choisissez un fichier à importer (1-{len(files)}): ")
        try:
            choice_index = int(choice) - 1
            if choice_index < 0 or choice_index >= len(files):
                raise ValueError("Choix invalide.")
            return os.path.join(dir_path, files[choice_index])
        except ValueError:
            raise ValueError("Choix invalide.")
