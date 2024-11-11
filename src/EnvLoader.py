import os
from dotenv import load_dotenv


class EnvLoader:
    """
    Loads and validates environment variables required for file paths and format selection.
    """

    def __init__(self):
        load_dotenv()
        self.injection_format = os.getenv('INJECTION_FORMAT', 'TXT').upper()
        self.full_context_json_path = os.getenv('FULL_CONTEXT_JSON_PATH')
        self.full_context_txt_path = os.getenv('FULL_CONTEXT_TXT_PATH')
        self.entries_dir = os.getenv('ENTRIES_DIR')
        self.metadatas_dir = os.getenv('METADATAS_DIR')
        self.take_notes_export_dir = os.getenv('TAKE_NOTES_EXPORT_DIR')

        self.validate_env_variables()

    def validate_env_variables(self):
        """Validates that all required environment variables are set properly."""
        if self.injection_format not in ['TXT', 'JSON']:
            raise ValueError("La variable INJECTION_FORMAT doit être 'TXT' ou 'JSON'.")
        if not all([self.entries_dir, self.metadatas_dir, self.take_notes_export_dir]):
            raise ValueError("Une ou plusieurs variables d'environnement sont manquantes ou incorrectes.")

    def get_paths_and_format(self):
        """Returns all paths and the selected format as a dictionary."""
        return {
            'injection_format': self.injection_format,
            'full_context_json_path': self.full_context_json_path,
            'full_context_txt_path': self.full_context_txt_path,
            'entries_dir': self.entries_dir,
            'metadatas_dir': self.metadatas_dir,
            'take_notes_export_dir': self.take_notes_export_dir,
        }
