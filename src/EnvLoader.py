import os
from dotenv import load_dotenv

class EnvLoader:
    """
    Loads and validates environment variables required for file paths.
    """
    def __init__(self):
        load_dotenv()
        self.full_context_json_path = os.getenv('FULL_CONTEXT_JSON_PATH')
        self.entries_dir = os.getenv('ENTRIES_DIR')
        self.metadatas_dir = os.getenv('METADATAS_DIR')
        self.take_notes_export_dir = os.getenv('TAKE_NOTES_EXPORT_DIR')

        self.validate_env_variables()

    def validate_env_variables(self):
        """Validates that all environment variables are set properly."""
        if not all([self.full_context_json_path, self.entries_dir, self.metadatas_dir, self.take_notes_export_dir]):
            raise ValueError("Une ou plusieurs variables d'environnement sont manquantes ou incorrectes.")

    def get_paths(self):
        """Returns all required paths as a dictionary."""
        return {
            'full_context_json_path': self.full_context_json_path,
            'entries_dir': self.entries_dir,
            'metadatas_dir': self.metadatas_dir,
            'take_notes_export_dir': self.take_notes_export_dir,
        }
