import os
from dotenv import load_dotenv

class EnvLoader:
    """
    Loads and validates environment variables required for file paths.
    """
    def __init__(self, env_path=None):
        """
        :param env_path: fichier de configuration à charger. **À fournir** : c'est
            le fichier que la page Paramètres écrit (``CONFIG_ENV_PATH``).

            Sans lui, ``load_dotenv()`` redécouvre le ``.env`` du dépôt en
            remontant depuis le répertoire courant, et la validation (qui lit
            ``CONFIG_ENV_PATH``) se retrouve à juger un fichier que le chargement
            n'utilise pas. Les deux divergent alors silencieusement : la page
            Paramètres affiche « configuration valide » pendant que l'injection
            échoue sur des chemins venus d'ailleurs.

            ``override=False`` est conservé : une variable d'environnement
            l'emporte sur le fichier, exactement comme dans
            ``backend.app.env_file.effective_settings``.
        """
        load_dotenv(env_path) if env_path else load_dotenv()
        self.full_context_json_path = os.getenv('FULL_CONTEXT_JSON_PATH')
        self.entries_dir = os.getenv('ENTRIES_DIR')
        self.metadatas_dir = os.getenv('METADATAS_DIR')
        self.take_notes_export_dir = os.getenv('TAKE_NOTES_EXPORT_DIR')
        self.pdf_export_file = os.getenv('PDF_EXPORT_FILE')

        self.validate_env_variables()

    def validate_env_variables(self):
        """Validates required env variables AND that their paths actually exist.

        On échoue tôt, au démarrage, avec un message qui liste précisément chaque
        problème (variable vide ou chemin introuvable) plutôt que de laisser le
        pipeline planter plus loin avec une erreur vague.
        """
        # 1. Variables obligatoires renseignées (non vides).
        # METADATAS_DIR est désormais FACULTATIF : les métadonnées étaient un vestige
        # du workflow ChatGPT (V1) et ne sont plus nécessaires. On ne bloque donc plus
        # le démarrage si le dossier n'est pas configuré.
        required = {
            'FULL_CONTEXT_JSON_PATH': self.full_context_json_path,
            'ENTRIES_DIR': self.entries_dir,
            'TAKE_NOTES_EXPORT_DIR': self.take_notes_export_dir,
        }
        missing_vars = [name for name, value in required.items() if not value]
        if missing_vars:
            raise ValueError(
                "Variables d'environnement manquantes ou vides dans le .env : "
                + ", ".join(missing_vars)
            )

        # 2. Existence effective des chemins (fichier attendu vs dossier attendu).
        path_checks = [
            ('FULL_CONTEXT_JSON_PATH', self.full_context_json_path, 'fichier'),
            ('ENTRIES_DIR', self.entries_dir, 'dossier'),
            ('TAKE_NOTES_EXPORT_DIR', self.take_notes_export_dir, 'dossier'),
        ]
        # METADATAS_DIR n'est vérifié que s'il est renseigné (facultatif, mais si on
        # le fournit il doit pointer sur un dossier réel).
        if self.metadatas_dir:
            path_checks.append(('METADATAS_DIR', self.metadatas_dir, 'dossier'))

        problems = []
        for name, path, kind in path_checks:
            exists = os.path.isfile(path) if kind == 'fichier' else os.path.isdir(path)
            if not exists:
                problems.append(f"  - {name} : {kind} introuvable -> {path}")
        if problems:
            raise ValueError(
                "Chemins introuvables (vérifiez le .env et l'accès au partage réseau) :\n"
                + "\n".join(problems)
            )

    def get_paths(self):
        """Returns all required paths as a dictionary."""
        return {
            'full_context_json_path': self.full_context_json_path,
            'entries_dir': self.entries_dir,
            'metadatas_dir': self.metadatas_dir,
            'take_notes_export_dir': self.take_notes_export_dir,
        }
