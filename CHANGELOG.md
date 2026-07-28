# Journal des modifications

Toutes les modifications notables de ce projet sont consignées dans ce fichier.

Le format s'inspire de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
et le projet suit un versionnage de type [SemVer](https://semver.org/lang/fr/)
(`MAJEUR.MINEUR.CORRECTIF`).

Catégories utilisées : **Ajouté**, **Modifié**, **Corrigé**, **Supprimé**,
**Déprécié**, **Sécurité**.

---

## [Non publié]

### Ajouté
- **Refactor backend/frontend — phase 1 : un backend structuré et une API JSON.**
  Première des trois phases d'une migration en *strangler* vers un backend et un
  frontend déployables séparément. L'application reste utilisable de bout en bout
  à chaque étape : l'interface HTMX existante n'a rien perdu.
  - **Frontend React/TypeScript autonome** (`frontend/`) : Vite, React Router,
    TanStack Query. Les cinq pages sont portées (Injecter, Historique, Détail,
    Touches, Paramètres) et l'ancienne interface HTMX est supprimée.
    - Le **client TypeScript est généré** depuis l'OpenAPI du backend
      (`npm run generate:api`) : le contrat n'est écrit qu'une fois, côté Pydantic,
      et une divergence devient une erreur de compilation plutôt qu'un bug à
      l'exécution.
    - Le **thème « grimoire » est porté tel quel** — mêmes variables, mêmes noms de
      classes, même rendu. Le choix d'une feuille globale plutôt que de CSS Modules
      est délibéré : ces classes sont déjà cloisonnées par convention de nommage.
    - Les **filtres de l'historique vivent dans l'URL** : un historique filtré reste
      partageable et le bouton « précédent » du navigateur fonctionne.
    - La **carte des touches gagne un filtre par famille et une recherche** d'action
      ou de mémo, instantanés — l'état complet arrive en un appel, là où l'ancienne
      interface rechargeait le clavier au serveur à chaque édition.
    - Le **sélecteur de date calcule tout localement**, bornes du mois comprises.
  - **Déploiement séparé en deux conteneurs** derrière Traefik, sur le même host :
    `PathPrefix(/api)` (priorité 100) vers le backend, catch-all (priorité 1) vers
    le frontend. Le navigateur reste donc en **same-origin** — aucune configuration
    CORS nulle part, en développement (proxy Vite) comme en production.
    - `backend/Dockerfile` ne copie plus que `backend/` ; `frontend/Dockerfile` est
      un build multi-étapes `node:22-alpine` → `nginx:alpine` (~75 Mo, sans runtime JS).
    - `nginx.conf` : repli SPA sur `index.html` pour les routes profondes, assets
      hashés en cache immuable, et `index.html` en `no-store` — un `index.html`
      périmé pointant vers des assets disparus est la cause classique de la page
      blanche après déploiement.
    - `deploy/Makefile` : `make logs|shell|restart S=<service>` pour cibler un seul
      conteneur ; `make check` rappelle que l'accès n'est pas authentifié.
  - `run_web.ps1` devient `run_dev.ps1` et lance les deux serveurs.
  - **API JSON versionnée `/api/v1`**, documentée sur `/api/docs` (OpenAPI sur
    `/api/openapi.json`) : santé, catégories, arcs, métadonnées, calendrier,
    injections (création, historique paginé, détail, PDF), carte des touches,
    paramètres. Les schémas Pydantic (`backend/app/schemas/`) sont la **seule**
    source du contrat — le client TypeScript de la phase 2 en sera généré.
  - Un **doublon** répond désormais `409 Conflict` avec le corps complet (journal
    d'exécution + injection existante) plutôt qu'un `200` portant `success: false` ;
    on force en rejouant le `POST` avec `allow_duplicate: true`.
  - Une **configuration invalide** répond `503` et non `500` : le service va bien,
    c'est son environnement qui ne va pas, et le client doit renvoyer vers la page
    Paramètres. `/api/v1/health` reste joignable dans ce cas — il ne dépend pas du
    service — pour que le frontend puisse diagnostiquer au lieu d'afficher une
    page blanche.
  - `GET /api/v1/calendar` renvoie **tout** le calendrier tamrielien en un appel, et
    `GET /api/v1/keymap` **tout** l'état de la carte des touches. Les allers-retours
    HTMX `/suggest-date`, `/date-days` et le rechargement du clavier à chaque
    édition de touche n'ont plus lieu d'être côté client.
- **Tests de l'orchestrateur et du contrat d'API** (`tests/test_injection_service.py`,
  `tests/test_api_*.py`, `tests/test_legacy_ui.py`, fixtures dans
  `tests/conftest.py`). `InjectionService` n'était couvert par aucun test alors
  qu'il porte l'invariant le plus important du projet — **le JSON n'est écrit
  qu'après le succès de l'injection XML** — qui est désormais verrouillé.
  Chaque test monte un environnement applicatif jetable ; aucune donnée réelle
  n'est touchée. La suite passe de 33 à 96 tests.
- `requirements-dev.txt` : dépendances de test, exclues de l'image de production.

### Modifié
- **`src/` devient `backend/core/`**, modules renommés en `snake_case` (PEP 8) —
  `InjectionService.py` → `injection_service.py`, etc. Aucun changement de logique.
- **Nouveau point d'entrée ASGI : `backend.app.main:app`** (au lieu de
  `webapp.main:app`). `Dockerfile` et `run_web.ps1` mis à jour.
- **Les singletons de module disparaissent au profit de `Depends`.**
  `webapp/main.py` (418 lignes) créait ses bases de données à l'import et
  reconstruisait la configuration à chaque requête via un `build_service()` global :
  rien n'était surchargeable, donc rien n'était testable sans toucher au vrai `.env`
  ni aux vraies bases. Tout passe désormais par `backend/app/deps.py`.
- **Réglages de déploiement typés** (`backend/app/config.py`, `pydantic-settings`),
  distingués des réglages applicatifs éditables : les premiers sont fixés au
  démarrage et mis en cache, les seconds sont relus à chaque requête puisque la
  page Paramètres peut les changer à chaud.
- `webapp/main.py` devient `webapp/ui.py` et passe de `FastAPI()` à `APIRouter` :
  l'API et l'UI vivent sur une seule application. Son retrait, une fois la SPA en
  place, sera une ligne à supprimer dans `create_app()`.
- Une **famille de touches inconnue** est maintenant refusée (`422`) au lieu d'être
  ignorée silencieusement : le formulaire semblait accepté alors que rien n'était
  écrit en base.
- L'historique et le détail n'exposent plus `pdf_path` en liste ; un booléen
  `has_pdf` suffit, le téléchargement passe par `/api/v1/injections/{id}/pdf`.

### Corrigé
- **La page Paramètres déclarait invalide une installation Docker correcte.**
  La validation ne lisait que le fichier `.env` — or en conteneur la configuration
  arrive par variables d'environnement (`env_file:` du compose) et le `.env` est
  exclu de l'image par `.dockerignore`. Tous les champs requis apparaissaient donc
  « Requis mais vide », le bandeau « Configuration incomplète » s'affichait et le
  bouton **Injecter était désactivé**. La validation lit désormais la configuration
  *effective* — variables d'environnement puis fichier, dans l'ordre de priorité que
  `EnvLoader` applique réellement.
- **Les paramètres saisis depuis l'interface étaient perdus à chaque rebuild.**
  L'écriture visait `<racine>/.env`, c'est-à-dire la couche d'image Docker. Le
  chemin est maintenant réglable via `CONFIG_ENV_PATH`, à pointer sur le volume
  persistant (`/data/app.env`) — `make check` le vérifie en pré-vol.
- `PUT /api/v1/settings` n'écrit que les clés déclarées : une requête ne peut pas
  injecter une variable arbitraire dans le fichier de configuration.
- **La validation et le chargement de la configuration lisaient deux fichiers
  différents.** `EnvLoader` faisait un `load_dotenv()` sans argument, qui
  redécouvre le `.env` du dépôt en remontant depuis le répertoire courant, pendant
  que la validation jugeait `CONFIG_ENV_PATH`. `/health` pouvait donc répondre
  « configuration valide » alors que l'injection échouait en `503` sur des chemins
  venus d'ailleurs — et en production, les chemins saisis depuis la page Paramètres
  n'auraient jamais été lus. `EnvLoader` reçoit désormais le chemin explicitement.
- **Un champ de configuration laissé vide cassait l'injection suivante.** La page
  Paramètres écrit une chaîne vide dans l'environnement pour un champ vide ;
  `os.getenv("MAX_TOKENS_PER_ENTRY", 500)` renvoyait alors `""` et non son défaut,
  et `int("")` levait **au milieu du pipeline**, après l'injection JSON en mémoire.
  L'utilisateur voyait « erreur lors de l'injection dans le XML », sans rapport avec
  la cause. Même correction pour `PDF_OUTPUT_PATH` et `PDF_EXPORT_FILE`.
- `GET /api/v1/metadata-files/{filename}` valide le nom **par appartenance** à la
  liste réelle du dossier plutôt que de le concaténer au chemin : un nom relatif ne
  correspond à aucune entrée et sort en `404`, sans lecture hors du dossier.

### Supprimé
- **L'interface en ligne de commande**, dépréciée depuis la 0.3.0 : `Main.py`,
  `src/LorePlexum.py`, `src/ShellPrinter.py`, `src/DataExtractor.py`,
  `run_tnfc.ps1`. Le pipeline reste identique, seul l'adaptateur console disparaît.
- `webapp/settings.py`, remplacé par `backend/app/env_file.py`.
- **L'interface HTMX** (`webapp/`) : gabarits Jinja2, feuille de style, HTMX
  vendorisé et `keymap.js`, remplacés par le frontend React.

### Sécurité
- L'application n'a **aucune authentification applicative** — choix explicite pour
  un outil mono-utilisateur. `PUT /api/v1/settings` écrivant des chemins du système
  de fichiers, la restriction doit être posée au **niveau réseau** (allowlist IP
  Traefik, VPN, Tailscale) avant toute exposition publique. `make check` et
  `DEPLOYMENT.md` le rappellent explicitement.

### Ajouté
- **Makefile de déploiement** (`deploy/Makefile`) : enveloppe les commandes de
  `DEPLOYMENT.md` (`make init` / `check` / `up` / `deploy` / `recreate` / `logs` /
  `shell` / `backup`), sans ajouter d'étape — les `docker compose` restent
  utilisables tels quels. `make check` est un **pré-vol** qui vérifie les
  prérequis silencieux (montage CIFS `/mnt/TakeNotes`, réseau Traefik `proxy`,
  variables obligatoires, bases pointant bien dans le volume `/data`) plutôt que
  de les laisser échouer dans les logs au démarrage. `make backup` archive les
  bases SQLite du volume dans `deploy/backups/` (ignoré par git).
- **Carte des touches** (`src/KeyboardLayout.py`, `src/KeyBinds.py`, page
  `Touches`) : addon déclaratif qui affiche un clavier AZERTY, un pavé numérique
  et une souris, et permet de noter l'action associée à chaque touche ainsi qu'un
  **mémo indiquant où elle se modifie** (MCM, `.ini`, `.json`) — l'information
  qu'on ne retrouve plus six mois plus tard. Purement documentaire : aucun fichier
  de jeu n'est lu ni écrit, aucun remappage, aucune capture clavier (l'assignation
  se fait au clic sur la touche affichée).
  - Les touches sont identifiées par leur **scan code DirectInput**, qui est aussi
    la clé primaire de la table : la règle « une touche = une action » est portée
    par le schéma, un conflit d'assignation est impossible par construction.
  - La disposition est **positionnelle** (base clavier US) : la touche A française
    porte le code 16, Z porte 17. C'est la confusion que le module neutralise, les
    mods lisant le code et jamais la lettre imprimée. Même logique pour les boutons
    latéraux de souris, libellés « Latéral haut / bas » plutôt que « M4 / M5 ».
  - Les familles (Déplacement, Vanilla, Combat, iEquip, Survie, Interface) vivent
    dans `KeyboardLayout.CATEGORIES` avec leurs couleurs ; celles-ci remontent au
    keycap en variables CSS inline, si bien qu'ajouter une famille ne demande
    aucune retouche de la feuille de style. Base amorcée au premier lancement avec
    le mapping Skyrim / Nolvus réel (27 touches), export JSON téléchargeable.
  - **En production, ajoutez `KEYBINDS_DB_PATH=/data/keybinds.db` à
    `deploy/app.env`** : sans cette ligne la base tombe sur son défaut relatif,
    est créée dans l'image et repart du semis à chaque reconstruction.
- **Calendrier tamrielien pour la date de session** (`src/TamrielicCalendar.py`) :
  le champ date libre est remplacé par des menus déroulants structurés (Mois, Jour,
  Ère, Année) reprenant les 12 mois du calendrier de *The Elder Scrolls*
  (Morning Star → Evening Star). Le formulaire assemble une date au format anglais
  compatible avec les XML existants (« Evening Star, 15th, 4E 201 »). Les menus sont
  pré-remplis à partir de la dernière date connue de la catégorie, en la décomposant
  (parsing tolérant aux anciens formats et aux noms de mois français). Réf. :
  <https://lagbt.wiwiland.net/index.php?title=Calendrier_tamrielien>.
- **Conteneurisation & déploiement Docker** (`Dockerfile`, `.dockerignore`,
  `deploy/`) : l'application peut tourner sur un serveur Docker distinct (ex.
  « hiatus ») et écrire sur le partage SMB (ex. « auditus ») monté en CIFS dans le
  conteneur. `deploy/docker-compose.yml` monte le partage (volume CIFS) et une base
  SQLite persistante (volume nommé), et **expose l'app via Traefik** (réseau externe
  `proxy`, labels de routage, `APP_HOST` paramétrable) sans publier de port ;
  gabarits d'environnement séparés
  (`deploy/.env.example` pour les secrets SMB, `deploy/app.env.example` pour la
  config appli) ; `deploy/DEPLOYMENT.md` documente le build, l'exécution et la
  **jonction de répertoire** côté PC de jeu pour partager le XML TakeNotes sans
  copie manuelle.

### Modifié
- **Exposition en HTTPS derrière Traefik** (`deploy/`) : l'application passe du
  suffixe DNS interne `*.core.home.arpa` — réservé par la RFC 8375, donc non
  résolu par certains appareils du réseau — à `*.sternum-lab.duckdns.org`. Le
  routeur Traefik écoute désormais sur l'entrypoint `websecure` avec le résolveur
  de certificat `duckdns` (wildcard Let's Encrypt via challenge DNS-01, aucun port
  ouvert sur internet). `APP_HOST` vaut par défaut
  `loreplexum.sternum-lab.duckdns.org` (aligné sur le nom du routeur Traefik, de
  l'image et du conteneur) et doit rester sur **un seul niveau** de sous-domaine,
  sans quoi le certificat wildcard ne s'applique pas.
- **Fin des balises `Resume :` / `Text :` dans le formulaire web** : l'interface
  propose désormais deux champs distincts — **Résumé** (facultatif) et **Texte du
  journal** (obligatoire) — au lieu d'un unique champ où il fallait baliser les
  sections. Le découpage par balises subsiste uniquement dans le CLI (déprécié), qui
  lit un texte brut ; `InjectionRequest` porte maintenant `resume` et `text` séparés,
  et `InjectionService` ne parse plus lui-même.
- **Génération PDF migrée de `pdfkit`/wkhtmltopdf vers WeasyPrint** : plus aucun
  binaire externe à installer (WeasyPrint est pur Python, s'appuyant sur des libs
  système Pango/Cairo fournies par l'image Docker). L'import de WeasyPrint est
  **différé** dans `generate_pdf()` pour qu'un poste sans ces libs (dev Windows)
  démarre quand même — seule la génération PDF est alors indisponible, de façon non
  bloquante. Numérotation des pages désormais gérée par les CSS Paged Media
  (`@page` + `counter`) au lieu du pied de page JavaScript de wkhtmltopdf.

### Supprimé
- Dépendance `pdfkit` et le prérequis binaire externe **wkhtmltopdf**.

---

## [0.3.0] - 2026-07-13

Refonte majeure : le script en ligne de commande interactif devient une
**application web locale** (FastAPI + HTMX) avec archivage des injections en base
de données. Le cœur métier a été entièrement **découplé du terminal** pour pouvoir
être piloté aussi bien par le web que par un adaptateur CLI.

### Ajouté
- **Interface web** (`webapp/`, FastAPI + HTMX, thème « grimoire ») avec trois pages :
  - **Injecter** : un formulaire unique regroupe les choix jadis dispersés en
    saisies terminal (catégorie, texte collé, arc, métadonnées, date). Soumission
    sans rechargement, journal d'exécution coloré et lien de téléchargement du PDF.
    La date de session se pré-remplit avec la dernière date connue de la catégorie.
  - **Historique** : tableau filtrable en direct (catégorie, arc, recherche
    plein-texte) avec pagination et page de détail par injection.
  - **Paramètres** : édition du `.env` avec validation en direct (✅/❌ selon
    l'existence réelle de chaque chemin), en remplacement de l'édition manuelle.
- **Archivage SQLite** (`src/Database.py`, classe `InjectionDatabase`) : chaque
  injection réussie est enregistrée (catégorie, arc, n° d'entrée, date de session,
  résumé, texte, métadonnées, XML, PDF, empreinte). Base locale `data/injections.db`
  (configurable via `DATABASE_PATH`).
- **Détection de doublon** : empreinte SHA-256 du texte injecté (`compute_text_hash`).
  Un texte déjà traité est signalé **avant toute écriture** ; l'injection n'a lieu
  qu'après confirmation explicite (bouton « Injecter malgré tout » / paramètre
  `allow_duplicate`).
- **Orchestrateur découplé** (`src/InjectionService.py`) : reçoit tous les
  paramètres d'un coup via `InjectionRequest` et renvoie un `InjectionResult`
  structuré (succès, logs, n° d'entrée, chemin PDF, doublon éventuel). Point
  d'entrée unique appelé par le web comme par le CLI. Ne lève jamais : les erreurs
  sont consignées et reflétées par `success=False`.
- **Collecteur de logs** (`src/Reporter.py`) : remplace `ShellPrinter` dans le
  cœur métier. Accumule les messages `(niveau, texte)` au lieu de les imprimer
  (écho console optionnel), afin que le même pipeline serve le terminal et le web.
- **Script de lancement web** (`run_web.ps1`) : active le venv, démarre Uvicorn et
  ouvre le navigateur sur `http://127.0.0.1:8000/`.
- **Dépendances web** (`requirements.txt`) : `fastapi`, `uvicorn`, `jinja2`,
  `python-multipart`. HTMX est vendorisé localement (`webapp/static/htmx.min.js`)
  pour un fonctionnement hors-ligne.

### Modifié
- **Découplage terminal du cœur métier** : toutes les décisions utilisateur qui
  étaient des `input()` au milieu du traitement deviennent des paramètres.
  - `src/XMLInjector.py` : `entry_date` et `max_tokens` passés en paramètres (fin
    de la saisie de date au milieu de l'injection) ; ajout de `get_last_date()`
    pour alimenter le champ par défaut de l'UI.
  - `src/JSONInjector.py` : le menu interactif `choose_arc` est remplacé par
    `list_arcs()` (lecture pour l'UI) et `resolve_arc()` (arc passé en paramètre :
    vide → nouvel arc auto, clé existante → réutilisée, nom inédit → créé).
  - `src/FileChooser.py` : le menu interactif devient l'utilitaire pur
    `list_files()` (l'interface présente la liste, le fichier choisi est un paramètre).
  - `src/DataExtractor.py` : injection d'un `Reporter` à la place de `ShellPrinter`.
  - `src/PDFExtractor.py` : `pdf_export_file` passé en paramètre (fin de
    l'instanciation interne d'`EnvLoader` qui revalidait tout le `.env`) ; `run()`
    retourne le chemin du PDF généré.
- **`src/LorePlexum.py`** : n'est plus l'orchestrateur monolithique mais un mince
  **adaptateur CLI** qui collecte les saisies console puis délègue à
  `InjectionService`. Prouve que le découplage fonctionne (même service que le web).
- **`.gitignore`** : ajout de `/data/` et `*.db` (base d'archivage locale).

### Déprécié
- **Interface en ligne de commande** (`Main.py`, `src/LorePlexum.py`,
  `src/ShellPrinter.py`) : conservée et fonctionnelle, mais supplantée par
  l'interface web. Elle sera retirée dans une version ultérieure.

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
