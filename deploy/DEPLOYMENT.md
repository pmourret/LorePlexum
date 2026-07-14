# Déploiement Docker — TNFCDataInjector

Ce document décrit le déploiement de l'application sur le serveur Docker
**hiatus**, écrivant sur le serveur SMB **auditus**, sans rien installer sur le PC
de jeu et avec l'app disponible en permanence.

## Vue d'ensemble

```
┌────────────────────┐   fstab CIFS (hôte)   ┌──────────────────────────────┐
│  hiatus            │  //auditus/…/TakeNotes │  auditus — …/TakeNotes/       │
│  /mnt/TakeNotes ───┼──────────────────────► │  _OUTPUT/ExportChapter1..5.xml ◄┐
│    │ bind-mount    │                        │  _APP/ENTRIES                 │ │
│    ▼               │                        │  _APP/FULL_CONTEXT_JSON       │ │
│  conteneur FastAPI │                        │  _APP/METADATAS · PDF_OUTPUT  │ │
│  + WeasyPrint      │                        └───────────────────────────────┼┘
│  :8000 (Traefik)   │                                                        │ jonction
└────────────────────┘                        ┌───────────────────────────────┴┐
                                              │  PC de jeu (Skyrim)             │
                                              │  …/FISS/TakeNotes --> auditus   │
                                              └─────────────────────────────────┘
```

- **L'hôte** monte le dossier TakeNotes d'auditus à `/mnt/TakeNotes` via
  `/etc/fstab` (mount.cifs + fichier de credentials). Le **conteneur bind-monte**
  ce dossier : Docker ne gère pas le CIFS lui-même (le driver de volume `local`
  utilise le syscall `mount`, qui ne connaît pas l'option `credentials=`).
- L'exposition HTTP passe par **Traefik** (réseau externe `proxy`) : aucun port
  n'est publié directement sur l'hôte.
- Le dossier **TakeNotes vit sur auditus**. Le PC de jeu y accède via une
  **jonction de répertoire** : le jeu croit lire son dossier local, mais lit/écrit
  en réalité sur auditus. L'app et le jeu partagent donc le même fichier, **sans
  aucune copie manuelle**.
- La base SQLite (historique + anti-doublon) vit dans un **volume Docker** nommé.

---

## 1. Prérequis sur hiatus

- Docker + Docker Compose v2.
- **Le dossier TakeNotes monté sur l'hôte à `/mnt/TakeNotes`** via `/etc/fstab`
  (paquet `cifs-utils` requis). Entrée fstab (avec fichier de credentials) :

  ```fstab
  //192.168.1.138/PERSONNEL_PIERRE/03_GAMES/01_SKYRIM_NOLVUS/03_TESV_ABYSSIAELLE/TakeNotes /mnt/TakeNotes cifs credentials=/home/pmourret_adm/.smbcredentials,uid=1000,gid=1000,_netdev 0 0
  ```

  Montez-le avant le premier run : `sudo mount /mnt/TakeNotes` (au boot, `_netdev`
  s'en charge). Vérifiez : `ls /mnt/TakeNotes` doit lister `_APP/`, `_OUTPUT/`…
- **Traefik** en service et le réseau Docker externe `proxy` déjà créé
  (`docker network create proxy` s'il n'existe pas), partagé avec les autres apps.

## 2. Configuration

Depuis `deploy/` :

```bash
cp .env.example .env          # une seule variable : APP_HOST (hôte Traefik)
cp app.env.example app.env    # config appli (chemins Linux sous /mnt/TakeNotes)
```

Éditez les deux fichiers. Ni `deploy/.env` ni `deploy/app.env` ne sont versionnés.

- `deploy/.env` → `APP_HOST` uniquement (le montage CIFS est géré par l'hôte, pas
  par Docker, donc plus d'identifiants SMB ici).
- `deploy/app.env` → chemins de l'app : XML dans `/mnt/TakeNotes/_OUTPUT`, données
  de l'appli sous `/mnt/TakeNotes/_APP/…`.

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

Le dossier monté `…\03_TESV_ABYSSIAELLE\TakeNotes` contient deux sous-dossiers :
`_OUTPUT` (les `ExportChapterN.xml`, cible de l'export du jeu) et `_APP` (données
de l'appli). La jonction doit donc pointer vers **`_OUTPUT`**, pour que le jeu
écrive ses XML là où l'app les lit (`TAKE_NOTES_EXPORT_DIR=/mnt/TakeNotes/_OUTPUT`).

1. **Déplacez** une première fois le contenu actuel de
   `…\Nolvus…\overwrite\SKSE\Plugins\FISS\TakeNotes` (les `ExportChapterN.xml`) vers
   auditus, dans `…\03_TESV_ABYSSIAELLE\TakeNotes\_OUTPUT`.
2. Ouvrez une invite **en administrateur** et créez le lien vers le chemin UNC :

   ```bat
   rmdir "G:\Nolvus_v5\Instances\Nolvus Ascension\MODS\overwrite\SKSE\Plugins\FISS\TakeNotes"
   mklink /D "G:\Nolvus_v5\Instances\Nolvus Ascension\MODS\overwrite\SKSE\Plugins\FISS\TakeNotes" "\\auditus.lan\PERSONNEL_PIERRE\03_GAMES\01_SKYRIM_NOLVUS\03_TESV_ABYSSIAELLE\TakeNotes\_OUTPUT"
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
