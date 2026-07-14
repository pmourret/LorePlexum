# Déploiement Docker — TNFCDataInjector

Ce document décrit le déploiement de l'application sur le serveur Docker
**hiatus**, écrivant sur le serveur SMB **auditus**, sans rien installer sur le PC
de jeu et avec l'app disponible en permanence.

## Vue d'ensemble

```
┌────────────────────┐        SMB/CIFS         ┌────────────────────────┐
│  hiatus (Docker)   │  ───── /mnt/auditus ──► │  auditus (stockage SMB)│
│  conteneur FastAPI │                         │  full_context.json     │
│  + WeasyPrint      │                         │  entries/ · metadatas/ │
│  :8000             │                         │  export_pdf/           │
└────────────────────┘                         │  TakeNotes/  (XML) ◄─┐ │
                                               └──────────────────────┼─┘
                                                                      │ jonction
                                               ┌──────────────────────┴─┐
                                               │  PC de jeu (Skyrim)     │
                                               │  …/TakeNotes  --> auditus│
                                               └─────────────────────────┘
```

- L'app tourne dans le conteneur et lit/écrit tous ses fichiers sur **auditus**
  (monté en CIFS sur `/mnt/auditus`).
- L'exposition HTTP passe par **Traefik** (réseau externe `proxy`) : aucun port
  n'est publié directement sur l'hôte.
- Le dossier XML **TakeNotes vit sur auditus**. Le PC de jeu y accède via une
  **jonction de répertoire** : le jeu croit lire son dossier local, mais lit/écrit
  en réalité sur auditus. L'app et le jeu partagent donc le même fichier, **sans
  aucune copie manuelle**.
- La base SQLite (historique + anti-doublon) vit dans un **volume Docker** nommé.

---

## 1. Prérequis sur hiatus

- Docker + Docker Compose v2.
- Le module noyau **CIFS** (paquet `cifs-utils` sur l'hôte) pour que le volume CIFS
  se monte.
- **Traefik** en service et le réseau Docker externe `proxy` déjà créé
  (`docker network create proxy` s'il n'existe pas), partagé avec les autres apps.

## 2. Configuration

Depuis `deploy/` :

```bash
cp .env.example .env          # secrets SMB (hôte, partage, identifiants)
cp app.env.example app.env    # config appli (chemins Linux sous /mnt/auditus)
```

Éditez les deux fichiers. Ni `deploy/.env` ni `deploy/app.env` ne sont versionnés.

- `deploy/.env` → `SMB_HOST`, `SMB_SHARE`, `SMB_USER`, `SMB_PASSWORD`, et
  `APP_HOST` (nom d'hôte Traefik, ex. `tnfc.core.home.arpa`).
- `deploy/app.env` → chemins de l'app. Le partage `SMB_SHARE` est monté à la racine
  de `/mnt/auditus`, donc `\\auditus\PERSONNEL_PIERRE\03_GAMES\…` devient
  `/mnt/auditus/03_GAMES/…`.

## 3. Build & run

```bash
cd deploy
docker compose up -d --build
docker compose logs -f        # vérifier le démarrage (validation des chemins .env)
```

L'interface est ensuite accessible via Traefik sur `http://<APP_HOST>/`
(ex. `http://tnfc.core.home.arpa/`), sans port à ouvrir sur l'hôte.

> Besoin d'un accès direct pour déboguer (hors Traefik) ? Ajoutez temporairement
> `ports: ["8000:8000"]` au service dans `docker-compose.yml`.

## 4. Mise à jour

```bash
cd deploy
git pull
docker compose up -d --build
```

Le volume `tnfc-data` (base SQLite) et les fichiers sur auditus survivent aux
reconstructions.

---

## Étape manuelle sur le PC de jeu : la jonction

Objectif : que le dossier TakeNotes du jeu pointe vers auditus, pour que
l'injection faite par hiatus soit vue par le jeu sans copie.

1. **Déplacez** une première fois le contenu actuel de
   `…\Nolvus…\overwrite\SKSE\Plugins\FISS\TakeNotes` vers l'emplacement retenu sur
   auditus (celui de `TAKE_NOTES_EXPORT_DIR`).
2. Ouvrez une invite **en administrateur** et créez le lien vers le chemin UNC :

   ```bat
   rmdir "G:\Nolvus_v5\Instances\Nolvus Ascension\MODS\overwrite\SKSE\Plugins\FISS\TakeNotes"
   mklink /D "G:\Nolvus_v5\Instances\Nolvus Ascension\MODS\overwrite\SKSE\Plugins\FISS\TakeNotes" "\\auditus.safe.home.arpa\PERSONNEL_PIERRE\03_GAMES\01_SKYRIM_NOLVUS\01_TAKENOTES\TakeNotes"
   ```

   > `mklink /D` crée un lien symbolique de répertoire, qui **supporte les cibles
   > UNC** (contrairement à une jonction `/J`). Si Windows refuse de suivre le lien
   > vers un partage distant, activez l'évaluation des liens distants (admin) :
   >
   > ```bat
   > fsutil behavior set SymlinkEvaluation R2R:1 R2L:1
   > ```

3. **⚠️ À valider par un test en jeu** avant de compter dessus : lancez une session,
   prenez une note, vérifiez que TakeNotes exporte bien le XML (fichier mis à jour
   sur auditus) puis le réimporte correctement. Si le mod FISS refuse le chemin
   distant, on bascule sur un agent de synchro (Syncthing) côté PC de jeu.

---

## Note « app dispo en permanence »

L'app écrit sur auditus à tout moment, PC de jeu éteint compris. Le jeu récupère
simplement la version à jour du XML à son prochain lancement (via la jonction).
Aucune file d'attente n'est nécessaire tant que la jonction est en place.
