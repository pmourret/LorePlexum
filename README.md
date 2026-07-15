# TNFCDataInjector — Projet Abyssiaelle

**Application web locale** qui réinjecte un texte de journal enrichi (issu d'une
session de jeu **Skyrim** annotée via le mod **TakeNotes**) à la fois dans un JSON
de contexte narratif complet et dans le fichier XML d'export TakeNotes de la
catégorie choisie, génère un PDF récapitulatif du journal, et **archive chaque
injection en base de données** (historique cherchable, détection des doublons).

> Depuis la version 0.3.0, l'outil s'utilise via une **interface web** (FastAPI +
> HTMX). L'ancienne interface en ligne de commande est conservée mais **dépréciée**
> (voir [Interface en ligne de commande (dépréciée)](#interface-en-ligne-de-commande-dépréciée)).

---

## Sommaire

- [Pipeline global](#pipeline-global)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration (`.env`)](#configuration-env)
- [Utilisation (interface web)](#utilisation-interface-web)
- [Archivage et détection de doublons](#archivage-et-détection-de-doublons)
- [Format des fichiers d'entrée](#format-des-fichiers-dentrée)
- [Catégories et fichiers XML](#catégories-et-fichiers-xml)
- [Sorties générées](#sorties-générées)
- [Interface en ligne de commande (dépréciée)](#interface-en-ligne-de-commande-dépréciée)
- [Dépannage](#dépannage)

---

## Pipeline global

1. **Session Skyrim jouée.**
2. **Prise de notes in-game** via le mod TakeNotes → export au format XML.
3. **Enrichissement narratif** du texte par une IA (Grok) → un résumé et un corps de
   journal (collés dans deux champs distincts côté web ; balises `Resume :` / `Text :`
   pour le CLI déprécié).
4. **Injection via l'interface web** → réinjecte le texte enrichi :
   - dans `full_context.json` (structure `character_arc > arc > journals`) ;
   - dans le fichier XML d'export TakeNotes de la catégorie choisie.
5. **Génération d'un PDF** récapitulatif du journal à partir du XML.
6. **Archivage en base** de l'injection (historique + empreinte anti-doublon).

> ⚠️ Le JSON n'est sauvegardé sur disque **qu'après** le succès de l'injection XML,
> afin que les deux fichiers ne divergent jamais silencieusement.

---

## Architecture

Le cœur métier est **découplé de toute interface** : il ne lit jamais le clavier et
n'imprime jamais dans un terminal. Toutes les décisions (catégorie, arc, date…)
sont des paramètres, et les messages sont *rapportés* à un `Reporter`. Le même cœur
sert donc l'interface web et l'adaptateur CLI.

### Cœur métier (`src/`)

| Fichier | Responsabilité |
|---|---|
| `src/InjectionService.py` | **Orchestrateur** du pipeline. Reçoit un `InjectionRequest`, renvoie un `InjectionResult` (succès, logs, n° d'entrée, PDF, doublon). Point d'entrée unique du web et du CLI. |
| `src/Reporter.py` | Collecte les messages `(niveau, texte)` du pipeline (écho console optionnel). Remplace `ShellPrinter` dans le métier. |
| `src/Database.py` (`InjectionDatabase`) | Archivage SQLite des injections + détection de doublons (empreinte SHA-256). |
| `src/EnvLoader.py` | Chargement / validation des variables d'environnement (`.env`). |
| `src/DataExtractor.py` | Extraction des sections `Resume :` / `Text :` d'un texte brut (utilisé par le **CLI déprécié** ; le web fournit deux champs séparés). |
| `src/TamrielicCalendar.py` | Calendrier de jeu (*The Elder Scrolls*) : mois, ères, jours ; formatage/parsing d'une date de session. |
| `src/JSONInjector.py` | Chargement, injection et sauvegarde du JSON de contexte. `list_arcs()` / `resolve_arc()`. |
| `src/XMLInjector.py` | Injection du texte dans le XML TakeNotes. Date et segmentation en paramètres ; `get_last_date()`. |
| `src/PDFExtractor.py` (`PDFGenerator`) | Génère un PDF récapitulatif à partir du XML. |
| `src/FileChooser.py` | Utilitaire `list_files()` (listing d'un dossier). |

### Interface web (`webapp/`)

| Fichier | Responsabilité |
|---|---|
| `webapp/main.py` | Application FastAPI : routes `Injecter`, `Historique`, `Détail`, `Paramètres`. |
| `webapp/settings.py` | Lecture / écriture / validation du `.env` depuis la page Paramètres. |
| `webapp/templates/` | Gabarits Jinja2 (HTMX pour l'interactivité sans rechargement). |
| `webapp/static/` | Feuille de style (thème « grimoire ») et HTMX vendorisé (hors-ligne). |

### Interface en ligne de commande (dépréciée)

| Fichier | Responsabilité |
|---|---|
| `Main.py` | Point d'entrée CLI (boucle d'exécution). |
| `src/LorePlexum.py` (`TNFCDataInjector`) | Adaptateur CLI : collecte les saisies console puis délègue à `InjectionService`. |
| `src/ShellPrinter.py` | Affichage coloré / emoji dans le terminal (utilisé par le CLI uniquement). |

---

## Prérequis

- **Python 3.12+**
- **WeasyPrint** — moteur de génération PDF, installé via pip (`requirements.txt`).
  Il ne requiert **aucun binaire externe** (il a remplacé `pdfkit`/`wkhtmltopdf`),
  mais s'appuie sur des **bibliothèques système** (Pango/Cairo/gdk-pixbuf).
  - **En production Docker** : ces libs sont fournies par l'image (rien à faire),
    voir [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md).
  - **En dev sous Windows** : les libs GTK ne sont pas présentes par défaut ;
    l'app démarre quand même, mais la génération du PDF est indisponible tant
    qu'elles ne sont pas installées (voir la doc WeasyPrint pour Windows).
  - En leur absence, l'injection réussit malgré tout ; seule la génération du PDF
    échoue (signalée dans le journal d'exécution, non bloquante).

---

## Installation

```powershell
# Depuis la racine du projet
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dépendances Python (voir `requirements.txt`) :

- `fastapi`, `uvicorn`, `jinja2`, `python-multipart` — interface web
- `weasyprint` — génération PDF (libs système Pango/Cairo, cf. [Prérequis](#prérequis))
- `python-dotenv` — chargement du `.env`
- `colorama`, `emoji`, `pyperclip` — utilisés par l'adaptateur CLI déprécié

HTMX est **vendorisé** dans `webapp/static/htmx.min.js` : aucune connexion Internet
n'est requise pour utiliser l'interface.

### Déploiement conteneurisé (Docker)

L'application peut être conteneurisée et déployée sur un serveur Docker distinct
(qui écrit sur le partage SMB), l'image embarquant WeasyPrint et ses libs système.
Voir [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md) : `Dockerfile`, `docker-compose.yml`
(montage CIFS du partage + volume SQLite persistant) et l'étape de jonction de
répertoire côté PC de jeu pour partager le XML TakeNotes sans copie manuelle.

---

## Configuration (`.env`)

La configuration se fait désormais depuis la page **Paramètres** de l'interface web,
qui lit et écrit le fichier `.env` à la racine et **valide en direct** l'existence
des chemins. Un gabarit est fourni dans `.env.struct`.

| Variable | Obligatoire | Description |
|---|:---:|---|
| `FULL_CONTEXT_JSON_PATH` | ✅ | Chemin du JSON de contexte complet (`full_context.json`). |
| `ENTRIES_DIR` | ✅ | Dossier contenant les fichiers texte enrichis. |
| `METADATAS_DIR` | — | Dossier des fichiers JSON de métadonnées. **Facultatif** (vestige V1/ChatGPT) : l'app démarre sans. |
| `TAKE_NOTES_EXPORT_DIR` | ✅ | Dossier des exports XML TakeNotes (`ExportChapterN.xml`). |
| `PDF_OUTPUT_PATH` | — | Dossier de sortie du PDF (défaut : `output/`). |
| `PDF_EXPORT_FILE` | — | Préfixe du nom de fichier PDF (le suffixe `_AAAA-MM-JJ.pdf` est ajouté). |
| `MAX_TOKENS_PER_ENTRY` | — | Largeur max d'un segment de texte XML (défaut : `500`). |
| `DATABASE_PATH` | — | Emplacement de la base d'archivage SQLite (défaut : `data/injections.db`). |

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

## Utilisation (interface web)

```powershell
.\run_web.ps1
```

Le script active le venv, démarre le serveur et ouvre le navigateur sur
<http://127.0.0.1:8000/>. Alternativement :

```powershell
python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8000
```

L'interface comporte trois pages :

### 1. Injecter

Un formulaire unique regroupe tous les choix (jadis des questions successives dans
le terminal) :

1. **Catégorie** (`journal`, `bestiaire`, `quetes`, `personnages`, `divers`).
2. **Résumé** *(facultatif)* et **Texte du journal** *(obligatoire)* : deux champs
   distincts collés directement — plus aucune balise `Resume :` / `Text :` à saisir.
3. **Arc** narratif : sélection d'un arc existant, ou saisie d'un nom pour créer un
   nouvel arc (laisser vide = nouvel arc auto-numéroté).
4. **Métadonnées** *(facultatif, hérité de la V1/ChatGPT)* : bloc dépliable ;
   choix d'un fichier de `METADATAS_DIR` **ou** JSON collé. Peut rester vide.
5. **Date de la session** — menus déroulants du **calendrier tamrielien** (Mois,
   Jour, Ère, Année), assemblés en `Evening Star, 15th, 4E 201`, pré-remplis avec la
   dernière date connue de la catégorie.

Le bouton **Injecter** exécute JSON + XML + PDF et affiche le **journal d'exécution**
coloré ainsi qu'un lien de téléchargement du PDF. Si le `.env` est invalide, la page
affiche un avertissement et renvoie vers **Paramètres** (aucun plantage).

### 2. Historique

Tableau de toutes les injections archivées, **filtrable en direct** par catégorie,
arc et recherche plein-texte (résumé / texte), avec pagination. Chaque ligne ouvre
une **page de détail** (texte injecté complet, métadonnées, lien PDF).

### 3. Paramètres

Édition du `.env` avec validation en direct : chaque chemin obligatoire est marqué
✅ (existe) ou ❌ (introuvable), en remplacement de l'édition manuelle du fichier.

---

## Archivage et détection de doublons

Chaque injection réussie est enregistrée dans une base **SQLite** locale
(`data/injections.db` par défaut) : catégorie, arc, n° d'entrée, date de session,
résumé, texte, métadonnées, fichier XML, chemin PDF et **empreinte SHA-256** du
texte injecté.

Avant toute écriture, l'empreinte du texte est comparée à celles déjà archivées :

- **Texte inédit** → injection normale.
- **Texte déjà injecté** → un avertissement indique la date et l'entrée existante,
  **et rien n'est écrit**. L'injection n'a lieu qu'après confirmation explicite via
  le bouton **« Injecter malgré tout »**.

La base est locale et ignorée par Git (`/data/`, `*.db`). Elle vit hors des partages
réseau où résident les JSON/XML.

---

## Format des fichiers d'entrée

### Texte enrichi

Un **résumé** (facultatif) et un **texte de journal** (obligatoire).

- **Interface web** : deux champs séparés — rien à baliser.
- **CLI déprécié** : le texte brut (presse-papiers ou fichier) doit contenir les
  sections `Resume :` (optionnelle) et `Text :` (obligatoire). Les labels tolèrent
  les accents et la casse (`Resume`/`Résumé`, `Text`/`Texte`) ; chaque section se
  termine à la première ligne vide (double saut de ligne) ou en fin de contenu.

```text
Resume : Bref résumé de l'entrée, une ou deux phrases.

Text : Corps complet du journal, enrichi narrativement.
```

### Fichier de métadonnées (`METADATAS_DIR`) — *facultatif, hérité*

> **Note.** Les métadonnées servaient à donner du contexte à ChatGPT (V1) pour
> garder la cohérence. Avec le workflow actuel elles ne sont plus nécessaires :
> elles restent uniquement **stockées** (champ `metadata` du JSON, colonne
> `metadata_json` de la base) et ne sont réinjectées nulle part. Le champ est
> désormais **optionnel** partout et le CLI ne le demande plus.

Un JSON libre décrivant le contexte de la scène (personnage, environnement,
émotions, détails sensoriels, conséquences…). Il est stocké tel quel dans le champ
`metadata` de l'entrée JSON. Dans l'interface web, il peut aussi être **collé
directement** au lieu d'être choisi parmi les fichiers.

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
- **Base d'archivage** — une ligne par injection dans `data/injections.db`.

---

## Interface en ligne de commande (dépréciée)

L'ancienne interface interactive reste fonctionnelle mais **est dépréciée** au
profit de l'interface web ; elle sera retirée dans une version ultérieure.

```powershell
python Main.py
# ou
.\run_tnfc.ps1
```

Elle guide l'utilisateur par une série de questions dans le terminal (catégorie,
source du texte — presse-papiers ou fichier —, arc, métadonnées, date), puis
exécute exactement le même pipeline que le web (via `InjectionService`). Le CLI gère
en plus l'archivage sur disque des fichiers traités (sous-dossiers `_traités/`), qui
n'a pas d'équivalent côté web.

---

## Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| La page Injecter affiche un avertissement de configuration | Un ou plusieurs chemins du `.env` sont vides ou introuvables. Corrigez-les dans **Paramètres** (les champs fautifs sont marqués ❌). |
| Échec de génération du PDF | Bibliothèques système de **WeasyPrint** (Pango/Cairo) absentes — fréquent en dev Windows (cf. [Prérequis](#prérequis)). En Docker, elles sont dans l'image. L'injection réussit malgré tout. |
| « Doublon détecté » alors que je veux réinjecter | Le texte a déjà été archivé. Utilisez **« Injecter malgré tout »** pour forcer. |
| `Texte après 'Text :' non trouvé` (CLI) | Le contenu collé n'a pas de section `Text :`. Côté web, remplissez le champ **Texte du journal**. |
| Le résumé est vide | Champ **Résumé** laissé vide côté web, ou section `Resume :` absente côté CLI (avertissement, non bloquant). |
| `Le fichier XML ... n'existe pas` | `TAKE_NOTES_EXPORT_DIR` incorrect ou fichier `ExportChapterN.xml` manquant. |
| Le port 8000 est déjà utilisé | Lancez Uvicorn sur un autre port : `--port 8001`. |
