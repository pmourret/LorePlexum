"""Couche pivot autoritative pour les fichiers XML FISS / TakeNotes.

Ce module est la SEULE porte d'entrée/sortie vers le format XML brut exporté par
le mod TakeNotes (FISS). Il isole tout le reste du code (XMLInjector,
PDFExtractor…) des pièges de ce format, qui n'a aucun schéma officiel et dont le
système d'export/import s'est révélé fragile à l'analyse manuelle des exports
réels (voir ``samples/``).

Principe : **lecture tolérante, écriture strictement native.**

- En lecture, on accepte des variations cosmétiques (casse des balises,
  déclaration XML éventuelle laissée par un ancien outil) pour survivre aux
  fichiers « legacy », mais on échoue BRUYAMMENT sur toute structure réellement
  ambiguë ou corrompue (paire ``Date``/``entry`` dépareillée, trou dans la
  numérotation, section ``<Data>`` absente…). Mieux vaut planter que réimporter
  dans le jeu un fichier qui a silencieusement perdu une entrée.
- En écriture, on re-sérialise TOUJOURS le document entier au format natif
  canonique (voir ``serialize``). C'est ce qui garantit un fichier cohérent et
  réimportable, quelle que soit la casse d'origine des balises.

----------------------------------------------------------------------------
PIÈGE n°1 — ``<NumberOfEntries>`` N'EST PAS un compte d'entrées
----------------------------------------------------------------------------
C'est l'**index de la PROCHAINE entrée à écrire**, soit ``nombre réel + 1``. Le
jeu ne le décrémente JAMAIS quand une entrée est supprimée : sur un fichier où
des entrées ont été effacées in-game, ce compteur est donc trop grand. Vérifié
5/5 sur des exports frais pris directement dans le jeu (``samples/``) :

    Chapter1 : 5 entrées → NumberOfEntries = 6
    Chapter2 : 1 entrée  → NumberOfEntries = 2
    Chapter3 : 0 entrée  → NumberOfEntries = 1
    Chapter4 : 0 entrée  → NumberOfEntries = 1
    Chapter5 : 2 entrées → NumberOfEntries = 3

=> On ne LIT jamais ``NumberOfEntries`` pour compter. On scanne les paires
   ``Date{N}``/``entry{N}`` séquentiellement à partir de 1 jusqu'à la première
   paire manquante (voir ``_scan_entries``). En écriture, on le RECALCULE
   toujours à ``len(entries) + 1`` (voir ``serialize``), y compris ``1`` pour un
   chapitre vide.

----------------------------------------------------------------------------
PIÈGE n°2 — ne JAMAIS « joliment indenter » un XML avant réimport
----------------------------------------------------------------------------
Le format natif du jeu est sur **une seule ligne**, sans déclaration XML, avec un
échappement d'entités bien précis (``&apos;``, ``&quot;``, ``&gt;`` et surtout
``&#x0D;`` pour les retours à la ligne). Un export retravaillé par un
pretty-printer externe (type Notepad++ XML Tools) est un format DÉGRADÉ : un tel
fichier, dans l'historique du projet, avait perdu une entrée par rapport à
l'export natif équivalent. Ce module ne produit donc JAMAIS de XML indenté :
``serialize`` émet une ligne unique, octet pour octet dans le style du jeu.

----------------------------------------------------------------------------
Casse des balises — incohérence VOLONTAIRE du format natif
----------------------------------------------------------------------------
Le jeu écrit ``<Date1>`` (D majuscule) mais ``<entry1>`` (e minuscule). Cette
asymétrie est reproduite à la lettre en écriture. En lecture on tolère les deux
casses.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from xml.etree import ElementTree as ET


class FissError(Exception):
    """Erreur bruyante sur un document FISS invalide ou ambigu.

    Levée plutôt que de risquer une lecture silencieusement fausse ou l'écriture
    d'un XML dégradé dans le dossier du jeu.
    """


# Valeurs d'en-tête natives observées dans tous les exports de samples/.
_DEFAULT_VERSION = "1.2"
_DEFAULT_MOD_NAME = "TakeNotesXML"


@dataclass
class FissEntry:
    """Une entrée du journal : une date et son texte (déjà dé-échappés)."""

    date: str
    text: str


@dataclass
class FissDocument:
    """Représentation en mémoire d'un export XML FISS / TakeNotes.

    Les entrées sont stockées dé-échappées (``&apos;`` -> ``'`` etc.). Le
    ré-échappement natif n'a lieu qu'au moment de ``serialize``.
    """

    version: str = _DEFAULT_VERSION
    mod_name: str = _DEFAULT_MOD_NAME
    entries: list[FissEntry] = field(default_factory=list)

    # ------------------------------------------------------------------ lecture
    @classmethod
    def load(cls, path: str) -> "FissDocument":
        """Charge un fichier XML FISS depuis le disque (lecture tolérante)."""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except OSError as exc:
            raise FissError(f"Impossible de lire le fichier XML « {path} » : {exc}") from exc
        return cls.parse(raw, source=path)

    @classmethod
    def parse(cls, raw: str, source: str = "<chaîne>") -> "FissDocument":
        """Parse une chaîne XML FISS. Échoue bruyamment si la structure est cassée.

        Tolère : la casse des balises (``Date``/``date``, ``entry``/``Entry``),
        une éventuelle déclaration ``<?xml ?>`` en tête (ignorée par ElementTree),
        des espaces cosmétiques. N'accepte PAS un document sans racine ``fiss`` ou
        sans section ``<Data>``, ni une numérotation de paires trouée.
        """
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise FissError(f"XML FISS mal formé dans « {source} » : {exc}") from exc

        if _local(root.tag).lower() != "fiss":
            raise FissError(
                f"Racine inattendue dans « {source} » : <{root.tag}> au lieu de <fiss>."
            )

        header = _find_ci(root, "Header")
        version = _text_of(_find_ci(header, "Version")) if header is not None else None
        mod_name = _text_of(_find_ci(header, "ModName")) if header is not None else None

        data = _find_ci(root, "Data")
        if data is None:
            raise FissError(f"Section <Data> absente dans « {source} ».")

        entries = cls._scan_entries(data, source)

        return cls(
            version=version or _DEFAULT_VERSION,
            mod_name=mod_name or _DEFAULT_MOD_NAME,
            entries=entries,
        )

    @staticmethod
    def _scan_entries(data: ET.Element, source: str) -> list[FissEntry]:
        """Scan séquentiel ``Date{N}``/``entry{N}`` — la SEULE source de vérité du compte.

        On ignore délibérément ``<NumberOfEntries>`` (voir le docstring du module).
        On repère toutes les balises ``date``/``entry`` (toutes casses) indexées,
        puis on avance de 1 en 1 : chaque cran doit avoir SES DEUX moitiés. À la
        première paire absente, on s'arrête — mais si des paires numérotées plus
        loin subsistent, c'est un trou (fichier corrompu / dégradé) et on plante.
        """
        dates: dict[int, str] = {}
        entries_by_n: dict[int, str] = {}
        for elem in data:
            name = _local(elem.tag)
            match = re.fullmatch(r"(date|entry)(\d+)", name, re.IGNORECASE)
            if not match:
                continue
            kind, number = match.group(1).lower(), int(match.group(2))
            if kind == "date":
                dates[number] = elem.text or ""
            else:
                entries_by_n[number] = elem.text or ""

        all_numbers = set(dates) | set(entries_by_n)
        if not all_numbers:
            return []

        result: list[FissEntry] = []
        index = 1
        while index in dates and index in entries_by_n:
            result.append(FissEntry(date=dates[index], text=entries_by_n[index]))
            index += 1

        # Toute balise indexée au-delà du dernier cran contigu = trou -> échec bruyant.
        leftover = {n for n in all_numbers if n >= index}
        if leftover:
            raise FissError(
                f"Numérotation Date/entry trouée dans « {source} » : arrêt à l'index "
                f"{index} mais balises restantes aux index {sorted(leftover)}. "
                "Fichier probablement corrompu ou dégradé par un pretty-print — "
                "aucune lecture n'est tentée pour éviter de perdre une entrée."
            )
        # Une moitié orpheline sur le cran d'arrêt (Date sans entry ou l'inverse).
        if index in dates or index in entries_by_n:
            raise FissError(
                f"Paire Date/entry dépareillée à l'index {index} dans « {source} » "
                "(une moitié manque). Échec bruyant plutôt que lecture partielle."
            )
        return result

    # ------------------------------------------------------------------ écriture
    @property
    def number_of_entries(self) -> int:
        """Valeur native de ``<NumberOfEntries>`` : index de la PROCHAINE entrée.

        = ``len(entries) + 1`` (jamais un simple ``len``). Vaut ``1`` pour un
        chapitre vide, conformément aux samples.
        """
        return len(self.entries) + 1

    def serialize(self) -> str:
        """Sérialise au format natif canonique : UNE ligne, pas de déclaration XML.

        Reproduit octet pour octet le style du jeu : casse asymétrique
        ``Date{N}``/``entry{N}``, ``<NumberOfEntries>`` recalculé, échappement
        d'entités natif (voir ``_escape``). Ne JAMAIS reformater/indenter la
        sortie (piège n°2 du docstring de module).
        """
        parts: list[str] = [
            "<fiss><Header><Version>",
            _escape(self.version),
            "</Version><ModName>",
            _escape(self.mod_name),
            "</ModName></Header><Data><NumberOfEntries>",
            str(self.number_of_entries),
            "</NumberOfEntries>",
        ]
        for index, entry in enumerate(self.entries, start=1):
            parts += [
                f"<Date{index}>", _escape(entry.date), f"</Date{index}>",
                f"<entry{index}>", _escape(entry.text), f"</entry{index}>",
            ]
        parts.append("</Data></fiss>")
        return "".join(parts)

    def save(self, path: str, backup: bool = True) -> str | None:
        """Écrit le document au format natif. Ne touche RIEN si la sortie est invalide.

        1. Sérialise en natif puis RE-VALIDE la chaîne (re-parse) : on refuse
           d'écrire un XML mal formé dans le dossier du jeu (échec bruyant).
        2. Sauvegarde optionnelle de l'original en ``.<timestamp>.bak`` avant
           écrasement (filet de sécurité contre une écriture dégradée / des
           fichiers ayant pu être édités à la main par le passé).
        3. Écriture UTF-8 SANS BOM, SANS ré-encodage des retours de ligne
           (``newline=""``) pour ne pas réintroduire de ``\\r``/``\\n`` littéraux.

        Retourne le chemin du backup créé, ou ``None`` si aucun.
        """
        payload = self.serialize()

        # Garde-fou : la sortie doit être un XML bien formé, sinon on n'écrit pas.
        try:
            ET.fromstring(payload)
        except ET.ParseError as exc:  # pragma: no cover - ne doit jamais arriver
            raise FissError(
                f"Refus d'écrire un XML mal formé dans « {path} » : {exc}"
            ) from exc

        backup_path: str | None = None
        if backup and os.path.exists(path):
            stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
            backup_path = f"{path}.{stamp}.bak"
            shutil.copy2(path, backup_path)

        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(payload)
        except OSError as exc:
            raise FissError(f"Échec de l'écriture de « {path} » : {exc}") from exc

        return backup_path


# --------------------------------------------------------------------- helpers
def _local(tag: str) -> str:
    """Retourne le nom local d'une balise (ElementTree préfixe les namespaces)."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_ci(parent: ET.Element | None, name: str) -> ET.Element | None:
    """Recherche d'un enfant direct par nom, insensible à la casse (lecture tolérante)."""
    if parent is None:
        return None
    target = name.lower()
    for child in parent:
        if _local(child.tag).lower() == target:
            return child
    return None


def _text_of(elem: ET.Element | None) -> str | None:
    return elem.text if elem is not None else None


def _escape(text: str) -> str:
    """Échappement d'entités au format natif du jeu.

    Reproduit exactement ce que produit l'export TakeNotes (vérifié sur
    ``samples/``) — et NON ce que produirait ``ElementTree`` :

    - ``&`` -> ``&amp;`` (EN PREMIER, sinon on ré-échapperait les ``&`` des
      entités qu'on vient d'insérer),
    - ``<`` -> ``&lt;``, ``>`` -> ``&gt;``,
    - ``"`` -> ``&quot;``, ``'`` -> ``&apos;`` (ElementTree, lui, laisse ``>``,
      ``"`` et ``'`` littéraux dans le contenu — d'où le sérialiseur maison),
    - tout retour à la ligne (``\\r\\n``, ``\\n`` ou ``\\r``) -> un unique
      ``&#x0D;`` (le jeu stocke les sauts de ligne comme un CR seul).
    """
    if text is None:
        text = ""
    # Normalise d'abord les fins de ligne en CR unique.
    text = text.replace("\r\n", "\r").replace("\n", "\r")
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    return text.replace("\r", "&#x0D;")
