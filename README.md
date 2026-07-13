# TNFCDataInjector — Projet Abyssiaelle

Outil en ligne de commande qui réinjecte un texte de journal enrichi (issu d'une
session de jeu **Skyrim** annotée via le mod **TakeNotes**) à la fois dans un JSON
de contexte narratif complet et dans le fichier XML d'export TakeNotes de la
catégorie choisie, puis génère un PDF récapitulatif du journal.

---

## Sommaire

- [Pipeline global](#pipeline-global)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration (`.env`)](#configuration-env)
- [Utilisation](#utilisation)
- [Format des fichiers d'entrée](#format-des-fichiers-dentrée)
- [Catégories et fichiers XML](#catégories-et-fichiers-xml)
- [Sorties générées](#sorties-générées)
- [Dépannage](#dépannage)

---

## Pipeline global

1. **Session Skyrim jouée.**
2. **Prise de notes in-game** via le mod TakeNotes → export au format XML.
3. **Enrichissement narratif** du texte par une IA (Grok) → texte formaté avec des
   sections `Resume :` et `Text :`.
4. **Exécution de ce script** → réinjecte le texte enrichi :
   - dans `full_context.json` (structure `character_arc > arc > journals`) ;
   - dans le fichier XML d'export TakeNotes de la catégorie choisie.
5. **Génération d'un PDF** récapitulatif du journal à partir du XML.

> ⚠️ Le JSON n'est sauvegardé sur disque **qu'après** le succès de l'injection XML,
> afin que les deux fichiers ne divergent jamais silencieusement.

---

## Architecture

| Fichier | Responsabilité |
|---|---|
| `Main.py` | Point d'entrée. Boucle d'exécution. |
| `src/LorePlexum.py` (`TNFCDataInjector`) | Orchestrateur du pipeline. |
| `src/EnvLoader.py` | Chargement / validation des variables d'environnement (`.env`). |
| `src/FileChooser.py` | Sélection interactive d'un fichier dans un dossier. |
| `src/DataExtractor.py` | Extraction des sections `Resume :` / `Text :` d'un fichier texte. |
| `src/JSONInjector.py` | Chargement, injection et sauvegarde du JSON de contexte complet. |
| `src/XMLInjector.py` | Injection du texte dans le XML d'export TakeNotes. |
| `src/PDFExtractor.py` (`PDFGenerator`) | Génère un PDF récapitulatif à partir du XML. |
| `src/ShellPrinter.py` | Affichage coloré / emoji dans le terminal. |

---

## Prérequis

- **Python 3.12+**
- **wkhtmltopdf** — binaire externe requis par `pdfkit` pour générer les PDF.
  **Il n'est pas installable via pip.**
  - Téléchargement : <https://wkhtmltopdf.org/downloads.html>
  - Sous Windows, il doit être accessible dans le `PATH` (chemin par défaut :
    `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`).

---

## Installation

```powershell
# Depuis la racine du projet
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dépendances Python (voir `requirements.txt`) :

- `colorama` — couleurs terminal (compatibilité Windows)
- `emoji` — emojis dans les messages
- `python-dotenv` — chargement du `.env`
- `pdfkit` — génération PDF (nécessite **wkhtmltopdf**, cf. [Prérequis](#prérequis))

---

## Configuration (`.env`)

Créez un fichier **`.env`** à la racine (le fichier doit s'appeler exactement `.env`
pour que `load_dotenv()` le trouve). Un gabarit est fourni dans `.env.struct`.

| Variable | Obligatoire | Description |
|---|:---:|---|
| `FULL_CONTEXT_JSON_PATH` | ✅ | Chemin du JSON de contexte complet (`full_context.json`). |
| `ENTRIES_DIR` | ✅ | Dossier contenant les fichiers texte enrichis à injecter. |
| `METADATAS_DIR` | ✅ | Dossier contenant les fichiers JSON de métadonnées. |
| `TAKE_NOTES_EXPORT_DIR` | ✅ | Dossier des exports XML TakeNotes (`ExportChapterN.xml`). |
| `PDF_OUTPUT_PATH` | — | Dossier de sortie du PDF (défaut : `output/Journal_Entries_By_Date.pdf`). |
| `PDF_EXPORT_FILE` | — | Préfixe du nom de fichier PDF (le suffixe `_AAAA-MM-JJ.pdf` est ajouté). |
| `MAX_TOKENS_PER_ENTRY` | — | Largeur max d'un segment de texte XML (défaut : `500`). |

Exemple :

```dotenv
FULL_CONTEXT_JSON_PATH=\\serveur\...\full_context.json
ENTRIES_DIR=\\serveur\...\entries
METADATAS_DIR=\\serveur\...\metadatas
TAKE_NOTES_EXPORT_DIR=G://...//TakeNotes
MAX_TOKENS_PER_ENTRY=1000
PDF_OUTPUT_PATH=\\serveur\...\export_pdf
PDF_EXPORT_FILE=ENTRIES
```

---

## Utilisation

```powershell
python Main.py
```

Ou via le script fourni (active le venv puis lance le script) :

```powershell
.\run_tnfc.ps1
```

Le script est **interactif** et vous guide étape par étape :

1. **Choix de la catégorie** (`journal`, `bestiaire`, `quetes`, `personnages`, `divers`).
2. **Choix du fichier texte** à injecter (dans `ENTRIES_DIR`).
3. **Choix de l'arc** narratif dans le JSON (ou création d'un nouvel arc).
4. **Choix du fichier de métadonnées** (dans `METADATAS_DIR`).
5. **Saisie de la date** de la session pour l'entrée (la dernière date connue est
   proposée par défaut ; appuyez sur Entrée pour la réutiliser). La date suit le
   calendrier du jeu, ex. `Evening Star, 15th, 4E 201`.
6. Injection JSON + XML, puis génération du PDF.

La boucle recommence après chaque injection ; fermez la fenêtre pour quitter.

---

## Format des fichiers d'entrée

### Fichier texte (`ENTRIES_DIR`)

Deux sections attendues. `Resume :` est **optionnel** (un avertissement s'affiche
s'il est absent) ; `Text :` est **obligatoire**. Les labels tolèrent les accents et
la casse (`Resume`/`Résumé`, `Text`/`Texte`). Chaque section se termine à la
première ligne vide (double saut de ligne) ou en fin de fichier.

```text
Resume : Bref résumé de l'entrée, une ou deux phrases.

Text : Corps complet du journal, enrichi narrativement.
```

### Fichier de métadonnées (`METADATAS_DIR`)

Un JSON libre décrivant le contexte de la scène (personnage, environnement,
émotions, détails sensoriels, conséquences…). Il est stocké tel quel dans le champ
`metadata` de l'entrée JSON.

---

## Catégories et fichiers XML

| Catégorie | Fichier XML |
|---|---|
| `journal` | `ExportChapter1.xml` |
| `bestiaire` | `ExportChapter2.xml` |
| `quetes` | `ExportChapter3.xml` |
| `personnages` | `ExportChapter4.xml` |
| `divers` | `ExportChapter5.xml` |

Structure XML TakeNotes (section `<Data>`) : paires `<dateN>` / `<entryN>` et un
compteur `<NumberOfEntries>`. Une entrée contenant `todo` est remplacée en priorité ;
sinon de nouvelles paires `dateN`/`entryN` sont ajoutées à la suite. Les textes trop
longs sont découpés en segments (`MAX_TOKENS_PER_ENTRY`) sans couper les mots.

---

## Sorties générées

- **`full_context.json`** — enrichi d'une nouvelle entrée dans
  `character_arc > <arc> > journals` (`entry_number`, `summary`, `text`, `metadata`).
- **Fichier XML de la catégorie** — nouvelles entrées datées.
- **PDF** — récapitulatif du journal regroupé par date, dans `PDF_OUTPUT_PATH`,
  nommé `<PDF_EXPORT_FILE>_<AAAA-MM-JJ>.pdf`.

---

## Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| `Une ou plusieurs variables d'environnement sont manquantes` | Vérifier le `.env` (nom exact, variables obligatoires renseignées). |
| Échec de génération du PDF | **wkhtmltopdf** non installé ou absent du `PATH` (cf. [Prérequis](#prérequis)). |
| `Texte après 'Text :' non trouvé` | Le fichier texte n'a pas de section `Text :`. |
| Le résumé est vide | Section `Resume :` absente (avertissement, non bloquant). |
| `Le fichier XML ... n'existe pas` | `TAKE_NOTES_EXPORT_DIR` incorrect ou fichier `ExportChapterN.xml` manquant. |
| Erreur d'encodage des emojis dans un flux redirigé | La console doit être en UTF-8 ; en usage normal (terminal PowerShell) l'affichage fonctionne. |
