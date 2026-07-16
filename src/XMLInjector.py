import os
import textwrap

from src.FissDocument import FissDocument, FissEntry, FissError
from src.Reporter import Reporter


class XMLInjector:
    """Injecte le texte enrichi dans le XML TakeNotes d'une catégorie.

    Toute la lecture/écriture du format XML brut FISS passe désormais par
    ``FissDocument`` (couche pivot autoritative) : cette classe ne manipule plus
    directement ``ElementTree``. On hérite ainsi de ses garanties —

    - le comptage des entrées vient du scan séquentiel ``Date{N}``/``entry{N}``,
      JAMAIS de ``<NumberOfEntries>`` (qui vaut ``nombre réel + 1`` et n'est pas
      décrémenté aux suppressions in-game) ;
    - l'écriture est strictement native (une ligne, pas de déclaration XML,
      échappement ``&apos;``/``&#x0D;``…, casse asymétrique ``Date``/``entry``),
      jamais reformatée/indentée (un pretty-print dégrade le fichier et peut lui
      faire perdre une entrée à la réimportation) ;
    - un original est sauvegardé en ``.bak`` avant tout écrasement, et rien n'est
      écrit si la sortie ne se re-parse pas (échec bruyant plutôt que silencieux).

    Voir ``src/FissDocument.py`` pour le détail de ces pièges.
    """

    def __init__(self, export_dir, reporter=None):
        self.export_dir = export_dir
        self.reporter = reporter or Reporter()

    def _resolve_xml_path(self, xml_file_name):
        """Normalise et valide le chemin du fichier XML de la catégorie."""
        xml_file_path = os.path.normpath(os.path.join(self.export_dir, xml_file_name))
        if not os.path.exists(xml_file_path):
            self.reporter.error(f"Le fichier XML {xml_file_path} n'existe pas.")
            raise FileNotFoundError(f"Le fichier XML {xml_file_path} n'existe pas.")
        return xml_file_path

    def get_last_date(self, xml_file_name):
        """Retourne la dernière date connue du XML (défaut proposé par l'UI).

        Sert au web pour pré-remplir le champ « date de session » sans rien
        injecter. Renvoie "" si le fichier n'existe pas, est illisible ou n'a
        aucune entrée datée.
        """
        try:
            xml_file_path = self._resolve_xml_path(xml_file_name)
            document = FissDocument.load(xml_file_path)
        except (FileNotFoundError, FissError):
            return ""
        return document.entries[-1].date if document.entries else ""

    def inject_text_in_xml(self, input_text, xml_file_name, entry_date=None, max_tokens=None):
        """Injecte le texte dans le XML de la catégorie.

        `entry_date` (date du calendrier de jeu) et `max_tokens` sont des
        paramètres explicites : la saisie interactive a disparu du cœur métier. Si
        `entry_date` est vide, on retombe sur la dernière date connue puis, à
        défaut, sur "DateAutomatique".

        Comportement conservé : un texte long est segmenté sans couper les mots ;
        une entrée existante contenant « todo » est remplacée en priorité ; les
        segments restants sont ajoutés en nouvelles paires ``Date{N}``/``entry{N}``.
        """
        if not input_text:
            self.reporter.error("Le texte d'entrée est vide ou None.")
            raise ValueError("Le texte d'entrée est vide ou None.")

        xml_file_path = self._resolve_xml_path(xml_file_name)

        # Lecture via la couche pivot : parse tolérant, échec bruyant si corrompu.
        try:
            document = FissDocument.load(xml_file_path)
        except FissError as exc:
            self.reporter.error(f"Erreur lors de la lecture du fichier XML : {exc}")
            raise ValueError(f"Erreur lors de la lecture du fichier XML : {exc}") from exc

        # Segmentation du texte sans couper les mots.
        if max_tokens is None:
            max_tokens = int(os.getenv("MAX_TOKENS_PER_ENTRY", 500))
        segments = textwrap.wrap(
            input_text, width=max_tokens, break_long_words=False, replace_whitespace=False
        )

        # Date réelle de la session : fournie par l'appelant, sinon dernière date
        # connue, sinon "DateAutomatique".
        entry_date = (entry_date or "").strip()
        if not entry_date and document.entries:
            entry_date = document.entries[-1].date
        if not entry_date:
            entry_date = "DateAutomatique"

        # Remplacement prioritaire des entrées TODO existantes.
        segments_processed = 0
        for position, entry in enumerate(document.entries, start=1):
            if segments_processed >= len(segments):
                break
            if entry.text and "todo" in entry.text.lower():
                entry.text = segments[segments_processed]
                self.reporter.success(
                    f"L'entrée TODO (entry{position}) a été remplacée par le texte complet."
                )
                segments_processed += 1

        # Ajout des segments restants comme nouvelles entrées.
        while segments_processed < len(segments):
            document.entries.append(FissEntry(date=entry_date, text=segments[segments_processed]))
            self.reporter.info(
                f"Nouvelle entrée XML ajoutée avec ID {len(document.entries)}."
            )
            segments_processed += 1

        # Écriture native (backup + revalidation gérés par la couche pivot).
        try:
            backup_path = document.save(xml_file_path, backup=True)
        except FissError as exc:
            self.reporter.error(f"Erreur lors de l'écriture du fichier XML : {exc}")
            raise ValueError(f"Erreur lors de l'écriture du fichier XML : {exc}") from exc

        if backup_path:
            self.reporter.info(f"Sauvegarde de l'original créée : {backup_path}")
        self.reporter.info(
            f"<NumberOfEntries> recalculé à {document.number_of_entries} "
            f"({len(document.entries)} entrée(s) réelle(s) + 1)."
        )
        self.reporter.success("L'injection dans le XML a été réalisée avec succès.")
