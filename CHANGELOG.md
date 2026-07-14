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
- **Conteneurisation & déploiement Docker** (`Dockerfile`, `.dockerignore`,
  `deploy/`) : l'application peut tourner sur un serveur Docker distinct (ex.
  « hiatus ») et écrire sur le partage SMB (ex. « auditus ») monté en CIFS dans le
  conteneur. `deploy/docker-compose.yml` monte le partage (volume CIFS) et une base
  SQLite persistante (volume nommé) ; gabarits d'environnement séparés
  (`deploy/.env.example` pour les secrets SMB, `deploy/app.env.example` pour la
  config appli) ; `deploy/DEPLOYMENT.md` documente le build, l'exécution et la
  **jonction de répertoire** côté PC de jeu pour partager le XML TakeNotes sans
  copie manuelle.

### Modifié
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
