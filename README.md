# TNFCDataInjector — Projet Abyssiaelle

**Application web locale** qui réinjecte un texte de journal enrichi (issu d'une
session de jeu **Skyrim** annotée via le mod **TakeNotes**) à la fois dans un JSON
de contexte narratif complet et dans le fichier XML d'export TakeNotes de la
catégorie choisie, génère un PDF récapitulatif du journal, et **archive chaque
injection en base de données** (historique cherchable, détection des doublons).

> L'outil se compose d'un **backend FastAPI** exposant une API JSON documentée sur
> `/api/docs`, et d'un **frontend React/TypeScript**, déployés en deux conteneurs
> derrière Traefik. L'ancienne interface HTMX et l'ancienne interface en ligne de
> commande ont été **supprimées**.

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
- [Développement et tests](#développement-et-tests)
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

Le projet est découpé en **trois couches**, dans un dépôt unique :

```
backend/core/   cœur métier — ne lit jamais le clavier, n'imprime jamais dans un terminal
backend/app/    couche HTTP — API JSON /api/v1, schémas Pydantic, dépendances
frontend/       SPA React/TypeScript — le seul consommateur de l'API aujourd'hui
```

Toutes les décisions (catégorie, arc, date…) sont des **paramètres**, et les messages
sont *rapportés* à un `Reporter` plutôt qu'imprimés. Le cœur ignore donc totalement
d'où viennent les données.

Le backend ne sert **aucune page** et le frontend ne connaît **aucun chemin de
fichier** : leur seul contact est le contrat d'API, dont le client TypeScript est
généré (voir [Développement et tests](#développement-et-tests)).

### Cœur métier (`backend/core/`)

| Fichier | Responsabilité |
|---|---|
| `injection_service.py` | **Orchestrateur** du pipeline. Reçoit un `InjectionRequest`, renvoie un `InjectionResult` (succès, logs, n° d'entrée, PDF, doublon). Point d'entrée unique de toutes les interfaces. |
| `reporter.py` | Collecte les messages `(niveau, texte)` du pipeline (écho console optionnel). |
| `database.py` (`InjectionDatabase`) | Archivage SQLite des injections + détection de doublons (empreinte SHA-256). |
| `env_loader.py` | Chargement / validation des chemins applicatifs depuis l'environnement. |
| `tamrielic_calendar.py` | Calendrier de jeu (*The Elder Scrolls*) : mois, ères, jours ; formatage/parsing d'une date de session. |
| `keyboard_layout.py` | Données pures de la **carte des touches** : familles (libellé + couleurs), disposition AZERTY en scan codes DirectInput, souris, mapping de départ. Ajouter une famille se fait ici et nulle part ailleurs. |
| `keybinds.py` (`KeyBindDatabase`) | Persistance SQLite de la carte des touches (`data/keybinds.db`). Le scan code est clé primaire : « une touche = une action » est garanti par le schéma. |
| `json_injector.py` | Chargement, injection et sauvegarde du JSON de contexte. `list_arcs()` / `resolve_arc()`. |
| `fiss_document.py` | **Couche pivot** du format XML FISS/TakeNotes : seule porte d'entrée/sortie du format brut. Lecture *tolérante* (casse, déclaration parasite), écriture *strictement native* (une ligne, pas de déclaration, échappement `&apos;`/`&#x0D;`…), comptage par scan séquentiel `Date{N}`/`entry{N}`, `.bak` avant écrasement, échec bruyant sur XML corrompu. |
| `xml_injector.py` | Injection du texte dans le XML TakeNotes (délègue tout le format à `fiss_document`). Date et segmentation en paramètres ; `get_last_date()`. |
| `pdf_extractor.py` (`PDFGenerator`) | Génère un PDF récapitulatif à partir du XML. |
| `files.py` | Utilitaire `list_files()` (listing d'un dossier). |

### Couche HTTP (`backend/app/`)

| Fichier | Responsabilité |
|---|---|
| `main.py` | `create_app()` : monte les routers sous `/api/v1` et traduit `ConfigurationError` en `503`. Point d'entrée ASGI. |
| `config.py` | `DeploymentSettings` : réglages fixés au démarrage (bases SQLite, `CONFIG_ENV_PATH`). |
| `env_file.py` | Lecture / écriture / validation de la configuration applicative éditable. |
| `deps.py` | Providers `Depends` (bases, reporter, service) et `ConfigurationError`. |
| `schemas/` | Modèles Pydantic — **la** source du contrat d'API, dont est généré le client TypeScript. |
| `routers/` | `context` (santé, catégories, arcs, calendrier), `injections`, `keybinds`, `settings`. |

L'API est documentée en ligne sur **`/api/docs`** (OpenAPI sur `/api/openapi.json`).

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/v1/health` | Santé + validité de la configuration |
| `GET` | `/api/v1/categories` | Catégories et fichiers XML visés |
| `GET` | `/api/v1/arcs` | Arcs existants dans le JSON de contexte |
| `GET` | `/api/v1/metadata-files` | Fichiers de métadonnées disponibles |
| `GET` | `/api/v1/calendar` | Calendrier tamrielien complet (statique) |
| `GET` | `/api/v1/calendar/suggest` | Dernière date connue d'une catégorie |
| `POST` | `/api/v1/injections` | Lance le pipeline → `201` / `409` doublon / `503` config |
| `GET` | `/api/v1/injections` | Historique paginé et filtrable |
| `GET` | `/api/v1/injections/facets` | Valeurs disponibles pour les filtres |
| `GET` | `/api/v1/injections/{id}` | Détail d'une injection |
| `GET` | `/api/v1/injections/{id}/pdf` | Téléchargement du PDF archivé |
| `GET` | `/api/v1/keymap` | État complet de la carte des touches |
| `PUT` `DELETE` | `/api/v1/keybinds/{scan_code}` | Assigne / libère une touche |
| `GET` | `/api/v1/keybinds/export` | Export JSON de la carte |
| `GET` `PUT` | `/api/v1/settings` | Configuration et validation |

Un doublon se signale par un **`409`** portant le corps complet (journal d'exécution
+ injection existante) ; on force l'injection en rejouant le `POST` avec
`allow_duplicate: true`. Une configuration invalide donne un **`503`** et non un
`500` : le service va bien, c'est son environnement qui ne va pas.

### Frontend (`frontend/`)

| Fichier | Responsabilité |
|---|---|
| `src/api/schema.d.ts` | Types **générés** depuis l'OpenAPI du backend. Jamais édité à la main. |
| `src/api/client.ts` | Enveloppe `fetch` typée + `ApiError` (qui distingue `409` doublon et `503` config). |
| `src/api/hooks.ts` | Hooks TanStack Query et clés de cache, regroupés pour que l'invalidation reste ciblée. |
| `src/pages/` | `InjectPage`, `HistoryPage`, `DetailPage`, `KeysPage`, `SettingsPage`. |
| `src/components/` | `Layout` (bandeau + alerte de configuration), `DateField`, composants partagés. |
| `src/styles/theme.css` | Thème « grimoire », porté tel quel depuis l'ancienne interface. |
| `nginx.conf` | Service des statiques : repli SPA, `index.html` en `no-store`, assets immuables. |

Deux points de conception valent d'être notés, parce qu'ils tirent parti de l'API
et n'étaient pas faisables avant :

- **Le calendrier est chargé une fois** (`GET /api/v1/calendar`) et le sélecteur de
  date calcule tout localement — bornes du mois comprises. Les deux allers-retours
  HTMX `/suggest-date` et `/date-days` ont disparu.
- **La carte des touches tient dans un seul appel** (`GET /api/v1/keymap`), ce qui
  rend possibles le filtre par famille et la recherche d'action : l'ancienne
  interface rechargeait le clavier entier au serveur à chaque édition.

### Déploiement

Deux conteneurs derrière Traefik, sur le **même host**, départagés par le chemin
via la priorité des routers :

| Chemin | Service | Image |
|---|---|---|
| `/api/…` | `backend` | `python:3.12-slim` + WeasyPrint. Seul à monter le partage et les bases. |
| tout le reste | `frontend` | build `node:22-alpine` → `nginx:alpine`. Aucun volume, aucune variable. |

Le navigateur reste donc toujours en **same-origin** : aucune configuration CORS
nulle part, en développement (proxy Vite) comme en production. Voir
[deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md).

> ⚠️ **Aucune authentification applicative.** `PUT /api/v1/settings` écrit des
> chemins du système de fichiers : l'accès doit être restreint au niveau réseau
> (allowlist IP Traefik, VPN, Tailscale) avant toute exposition publique.

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

- `fastapi`, `uvicorn`, `jinja2`, `python-multipart` — couche web
- `pydantic-settings` — réglages de déploiement typés
- `weasyprint` — génération PDF (libs système Pango/Cairo, cf. [Prérequis](#prérequis))
- `python-dotenv` — chargement de la configuration
- `colorama` — écho console optionnel du `Reporter`

Les dépendances de test (`pytest`, `httpx`) vivent dans `requirements-dev.txt` et
ne sont pas installées dans l'image de production.

Le frontend se construit avec Node 22 (`cd frontend && npm ci`). Aucune ressource
n'est chargée depuis Internet à l'exécution : polices système, pas de CDN.

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
.\run_dev.ps1
```

Le script lance les **deux** serveurs — backend Uvicorn sur `:8000`, frontend Vite
sur `:5173` — et ouvre le navigateur sur <http://localhost:5173/>. Le proxy Vite
renvoie `/api` vers le backend, donc le navigateur reste en same-origin comme en
production. Alternativement, dans deux terminaux :

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend ; npm run dev
```

`.\run_dev.ps1 -Backend` ne lance que l'API et ouvre `/api/docs` : pratique pour
explorer le contrat sans passer par l'interface.

L'interface comporte quatre pages :

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

Les filtres vivent dans l'URL (`?categorie=&arc=&search=&page=`) : un historique
filtré reste partageable et le bouton « précédent » du navigateur fait ce qu'on
attend.

### 3. Touches

Mémo de l'assignation Skyrim / Nolvus : clavier AZERTY, pavé numérique et souris.
Un clic sur une touche ouvre l'éditeur (action, famille, mémo). Le **mémo** répond
à « où se modifie cette touche ? » (MCM, `.ini`, `.json`) — l'information qu'on ne
retrouve plus six mois après.

Filtre par famille (clic sur la légende) et recherche d'action ou de mémo, tous
deux instantanés : l'état complet de la carte arrive en un seul appel. Purement
documentaire, aucun fichier de jeu n'est lu ni écrit.

### 4. Paramètres

Édition de la configuration avec validation en direct : chaque chemin obligatoire
est marqué ✅ (existe) ou ❌ (introuvable), en remplacement de l'édition manuelle
du fichier.

La validation porte sur la configuration **effective** — variables d'environnement
puis fichier, dans l'ordre de priorité réellement appliqué. Une valeur fournie par
l'environnement (le cas en conteneur) apparaît donc bien comme valide.

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

Structure XML TakeNotes (section `<Data>`) : paires `<DateN>` / `<entryN>` et un
compteur `<NumberOfEntries>`. Une entrée contenant `todo` est remplacée en priorité ;
sinon de nouvelles paires `DateN`/`entryN` sont ajoutées à la suite. Les textes trop
longs sont découpés en segments (`MAX_TOKENS_PER_ENTRY`) sans couper les mots.

### Format natif FISS — pièges à connaître

Le format XML brut du mod TakeNotes/FISS n'a **aucun schéma officiel**. Son analyse
sur des exports réels (`samples/`) a révélé des pièges que la couche pivot
`backend/core/fiss_document.py` neutralise — **à ne jamais réintroduire ailleurs** :

- **`<NumberOfEntries>` n'est PAS le nombre d'entrées.** C'est l'**index de la
  prochaine entrée à écrire** (= nombre réel **+ 1**), jamais décrémenté quand une
  entrée est supprimée in-game (donc parfois trop grand). Vérifié 5/5 sur des
  exports frais. ⇒ On ne le lit **jamais** pour compter : le nombre réel vient du
  **scan séquentiel** des paires `Date{N}`/`entry{N}` depuis 1 jusqu'à la première
  paire manquante. En écriture il est **recalculé** à `entrées + 1` (`1` si vide).
- **Casse asymétrique volontaire** : le jeu écrit `<Date1>` (D **majuscule**) mais
  `<entry1>` (e **minuscule**). Reproduit à la lettre en écriture ; les deux casses
  sont tolérées en lecture (fichiers *legacy*).
- **Ne jamais « joliment indenter » un XML avant réimport.** Le format natif tient
  sur **une seule ligne**, sans déclaration `<?xml ?>`, avec un échappement précis
  (`&apos;`, `&quot;`, `&gt;`, `&#x0D;` pour les retours à la ligne). Un export
  repassé dans un pretty-printer externe (type Notepad++ XML Tools) est **dégradé**
  et a déjà, dans l'historique du projet, **perdu une entrée** face à l'export natif
  équivalent. La couche pivot écrit toujours en format natif et ne reformate jamais.
- **Filets de sécurité** : avant tout écrasement, l'original est copié en
  `.<horodatage>.bak` ; et rien n'est écrit si la sortie ne se re-parse pas
  (échec bruyant plutôt que silencieux).

Tests de référence adossés aux 5 exports de `samples/` : `tests/` (lancer
`python -m unittest discover -s tests`), couvrant chapitre vide / 1 entrée /
plusieurs entrées, le round-trip natif octet-pour-octet et le recalcul de
`<NumberOfEntries>`.

---

## Sorties générées

- **`full_context.json`** — enrichi d'une nouvelle entrée dans
  `character_arc > <arc> > journals` (`entry_number`, `summary`, `text`, `metadata`).
- **Fichier XML de la catégorie** — nouvelles entrées datées.
- **PDF** — récapitulatif du journal regroupé par date, dans `PDF_OUTPUT_PATH`,
  nommé `<PDF_EXPORT_FILE>_<AAAA-MM-JJ>.pdf`.
- **Base d'archivage** — une ligne par injection dans `data/injections.db`.

---

## Développement et tests

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -q
```

| Fichier | Couvre |
|---|---|
| `tests/test_fiss_document.py` | La couche pivot du format XML FISS (lecture tolérante, écriture native, comptage). |
| `tests/test_xml_injector.py` | L'injection XML au-dessus de la couche pivot (segmentation, TODO, `.bak`). |
| `tests/test_injection_service.py` | L'orchestrateur et ses invariants — dont **le JSON n'est jamais écrit si le XML échoue**. |
| `tests/test_api_*.py` | Le contrat HTTP : codes de statut, forme des corps, `409` doublon, `503` config, traversée de chemin. |

Les fixtures (`tests/conftest.py`) montent un environnement applicatif jetable par
test : copies des exports de `samples/`, JSON de contexte neuf, bases SQLite vierges.
Aucune donnée réelle du projet n'est touchée.

### Frontend

```powershell
cd frontend
npm ci
npm run generate:api     # regenere src/api/schema.d.ts depuis l'OpenAPI du backend
npm run typecheck
npm run build
```

**`npm run generate:api` est à relancer dès qu'un schéma Pydantic change.** Le
contrat n'est écrit qu'une fois, côté backend ; une divergence se manifeste alors
en erreur de compilation TypeScript plutôt qu'en bug à l'exécution.

> `npm audit` signale un avis sur `react-router` en mode **RSC** (React Server
> Components). Cette application est une SPA statique servie par nginx : ni SSR,
> ni server actions, donc le code concerné n'est jamais exécuté. Rester sur la
> version épinglée est délibéré — la version « corrigée » proposée (7.11.0)
> réintroduit un *open redirect* dans `<Link>`, lui bien atteignable côté client.

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
