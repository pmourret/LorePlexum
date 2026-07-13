import re

from src.Reporter import Reporter


class DataExtractor:
    """
    Extracts sections of text from a given file.
    """
    def __init__(self, reporter=None):
        # Un reporter par défaut sans écho : le métier ne dépend plus du terminal.
        self.reporter = reporter or Reporter()

    def extract_text_sections(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except FileNotFoundError:
            self.reporter.error(f"Le fichier {file_path} n'existe pas.")
            raise
        except Exception as e:
            self.reporter.error(f"Erreur lors de la lecture du fichier : {e}")
            raise

        # Le parsing lui-même est délégué : même logique que la source presse-papiers.
        return self.extract_text_sections_from_content(content)

    def extract_text_sections_from_content(self, content):
        """Extrait les sections Resume/Text depuis un texte brut.

        Utilisé aussi bien pour un fichier (via extract_text_sections) que pour le
        contenu du presse-papiers, afin que les deux sources partagent exactement le
        même parsing tolérant aux accents et à la casse.
        """
        try:
            # Labels tolérants aux accents et à la casse : "Resume :", "Résumé :",
            # "Text :", "Texte :", etc. Les deux sections sont traitées de la même
            # façon pour éviter les incohérences d'extraction.
            resume_match = re.search(r'R[ée]sum[ée]\s*:\s*(.*?)(?:\n{2,}|$)', content, re.DOTALL | re.IGNORECASE)
            text_match = re.search(r'Texte?\s*:\s*(.*?)(?:\n{2,}|$)', content, re.DOTALL | re.IGNORECASE)

            resume_text = resume_match.group(1).strip() if resume_match else ""
            main_text = text_match.group(1).strip() if text_match else ""

            # Le résumé est optionnel : on avertit explicitement plutôt que d'échouer
            # en silence (chaîne vide sans message).
            if not resume_text:
                self.reporter.warning("Aucune section 'Resume :' trouvée : le résumé sera vide.")

            # Le texte principal est obligatoire.
            if not main_text:
                self.reporter.error("Texte après 'Text :' non trouvé dans le contenu.")
                raise ValueError("Texte après 'Text :' non trouvé dans le contenu.")

            self.reporter.success("Extraction des sections de texte réussie.")
            return resume_text, main_text

        except ValueError:
            # Erreur métier déjà signalée : on la propage telle quelle.
            raise
        except Exception as e:
            self.reporter.error(f"Erreur lors de l'extraction des sections de texte : {e}")
            raise
