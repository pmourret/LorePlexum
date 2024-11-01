import re

class DataExtractor:
    """
    Extracts sections of text from a given file.
    """
    @staticmethod
    def extract_text_sections(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            resume_match = re.search(r'Resume :\s*(.*?)(?:\n{2,}|$)', content, re.DOTALL)
            text_match = re.search(r'Text :\s*(.*?)(?:\n{2,}|$)', content, re.DOTALL)

            resume_text = resume_match.group(1).strip() if resume_match else ""
            main_text = text_match.group(1).strip() if text_match else ""

            if not main_text:
                raise ValueError("Texte après 'Text:' non trouvé dans le fichier.")

            return resume_text, main_text
