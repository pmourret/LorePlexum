import os


class FileChooser:
    """
    Utilitaire de listing de fichiers d'un dossier.

    L'ancienne sélection interactive (menu numéroté dans le terminal) a été retirée :
    la couche d'interface (web ou CLI) présente la liste et renvoie le fichier choisi
    en paramètre au pipeline. Ici on ne fait plus que lister.
    """

    @staticmethod
    def list_files(dir_path):
        """Retourne les noms de fichiers du dossier (hors sous-dossiers), triés.

        Lève FileNotFoundError si le dossier est vide, comportement attendu par les
        appelants existants.
        """
        files = sorted(
            f for f in os.listdir(dir_path)
            if os.path.isfile(os.path.join(dir_path, f))
        )
        if not files:
            raise FileNotFoundError(f"Aucun fichier trouvé dans le répertoire '{dir_path}'.")
        return files
