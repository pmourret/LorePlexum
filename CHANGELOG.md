# Journal des modifications

Toutes les modifications notables de ce projet sont consignées dans ce fichier.

Le format s'inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
et le projet suit un versionnage de type [SemVer](https://semver.org/lang/fr/)
(`MAJEUR.MINEUR.CORRECTIF`).

Catégories utilisées : **Ajouté**, **Modifié**, **Corrigé**, **Supprimé**,
**Déprécié**, **Sécurité**.

---

## [Non publié]

_Rien pour l'instant._

---

## [0.2.0] - 2026-07-13

Session de nettoyage et de durcissement du script existant (sans refonte
d'architecture). Correction des bugs bloquants pour la Session 001.

### Corrigé
- **Désynchronisation JSON/XML** (`src/LorePlexum.py`) : le JSON de contexte
  n'est désormais sauvegardé sur disque **qu'après** le succès de l'injection XML.
  En cas d'échec du XML, le JSON n'est plus écrit — les deux fichiers restent
  synchronisés. La capture d'exception a été élargie de `ValueError` à
  `Exception` pour couvrir aussi `FileNotFoundError` (XML absent).
- **Dépendance PDF incorrecte** (`requirements.txt`) : `reportlab` (jamais
  importé) remplacé par `pdfkit==1.0.0` (réellement utilisé). Fichier réencodé
  en UTF-8 (il était en UTF-16). Le prérequis binaire externe **wkhtmltopdf**
  (non installable via pip) est désormais documenté.
- **Date des entrées XML jamais réellement définie** (`src/XMLInjector.py`) :
  ajout d'une saisie utilisateur de la date réelle de la session (calendrier de
  jeu, ex. `Evening Star, 15th, 4E 201`), la dernière date connue étant proposée
  par défaut. Fin du `"DateAutomatique"` recopié silencieusement.
- **Extraction de texte incohérente** (`src/DataExtractor.py`) : les labels
  `Resume :` / `Text :` tolèrent maintenant les accents et la casse
  (`Résumé`, `Texte`…). Un résumé absent déclenche un avertissement explicite
  au lieu d'un échec silencieux ; le texte principal reste obligatoire.
- **Typo dans le titre du PDF** (`src/PDFExtractor.py`) :
  `Journal d'Abyssiaelle'` → `Journal d'Abyssiaelle`.
- **Import inutilisé** (`Main.py`) : suppression de `from colorama import Fore`.

### Ajouté
- **Validation des chemins au démarrage** (`src/EnvLoader.py`) : en plus de
  vérifier que les variables obligatoires sont renseignées, `EnvLoader` contrôle
  désormais que chaque chemin existe réellement (fichier vs dossier) et lève une
  erreur listant précisément les chemins manquants — au lieu d'un échec tardif et
  flou dans le pipeline.
- **`README.md`** : documentation complète (pipeline, architecture, prérequis,
  installation, configuration `.env`, utilisation, formats d'entrée, dépannage).
- **`CHANGELOG.md`** : ce fichier de suivi des modifications.

### Notes de configuration
- Les chemins réseau du `.env` (`FULL_CONTEXT_JSON_PATH`, `ENTRIES_DIR`,
  `METADATAS_DIR`) pointaient vers des emplacements périmés (données déplacées
  dans le sous-dossier `.old\`). Correction de configuration à effectuer dans le
  `.env` (hors code). La nouvelle validation `EnvLoader` signale précisément les
  chemins fautifs.

---

## [0.1.0] - 2024-11-15

Ligne de base : premier état fonctionnel du script (avant suivi de version).

### Ajouté
- Pipeline complet : sélection de catégorie et de fichier, extraction des
  sections `Resume :` / `Text :`, injection dans le JSON de contexte
  (`character_arc > arc > journals`) et dans le XML d'export TakeNotes.
- Génération d'un PDF récapitulatif du journal via `pdfkit`
  (`src/PDFExtractor.py`, classe `PDFGenerator`).
- Affichage terminal coloré avec emojis (`src/ShellPrinter.py`, `colorama`).
- Chargement des variables d'environnement via `.env` (`src/EnvLoader.py`).
