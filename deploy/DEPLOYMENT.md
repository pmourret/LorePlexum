# Déploiement Docker — LorePlexum

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
│  backend  (FastAPI │                        │  _APP/METADATAS · PDF_OUTPUT  │ │
│   + WeasyPrint)    │                        └───────────────────────────────┼┘
│  frontend (nginx)  │                                                        │ jonction
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
- **Deux conteneurs**, départagés par le chemin sur le même host :

  | Chemin | Service | Rôle |
  |---|---|---|
  | `/api/…` | `backend` | API FastAPI. Seul à monter le partage et les bases. |
  | tout le reste | `frontend` | SPA React construite, servie par nginx. Aucun volume. |

  La priorité des routers Traefik (`100` pour l'API, `1` pour le catch-all) fait
  le tri. Comme les deux répondent sur le même host, le navigateur reste en
  **same-origin** : aucune configuration CORS n'est nécessaire.

> ### ⚠️ Accès — à lire avant toute exposition
>
> L'application n'a **aucune authentification applicative**, et `PUT /api/v1/settings`
> écrit des chemins du système de fichiers. La restriction doit donc être posée au
> niveau réseau, **avant** d'ouvrir l'accès : middleware `ipallowlist` Traefik,
> VPN, ou Tailscale. C'est un choix assumé pour un outil mono-utilisateur ; il
> cesse de l'être dès que l'URL est joignable depuis Internet.

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
make init                     # copie les deux .example (n'écrase jamais l'existant)
```

Éditez les deux fichiers, puis `make check` pour valider. Ni `deploy/.env` ni
`deploy/app.env` ne sont versionnés.

> Sans `make`, l'équivalent manuel reste :
> `cp .env.example .env && cp app.env.example app.env`

- `deploy/.env` → `APP_HOST` uniquement (le montage CIFS est géré par l'hôte, pas
  par Docker, donc plus d'identifiants SMB ici).
- `deploy/app.env` → chemins de l'app : XML dans `/mnt/TakeNotes/_OUTPUT`, données
  de l'appli sous `/mnt/TakeNotes/_APP/…`.

## 3. Build & run

```bash
cd deploy
make check                    # pré-vol : montage, réseau proxy, variables
make up                       # équivaut à docker compose up -d --build
make logs                     # vérifier le démarrage (validation des chemins .env)
```

`make` seul liste toutes les cibles. Les commandes `docker compose` restent
utilisables directement : le Makefile ne fait que les envelopper, il n'introduit
aucune étape supplémentaire.

| Cible | Équivalent |
|---|---|
| `make up` | `docker compose up -d --build` (précédé de `make check`) |
| `make deploy` | `git pull` puis `make up` — le flux de mise à jour nominal |
| `make recreate` | `docker compose up -d --build --force-recreate` |
| `make down` / `restart` / `logs` / `ps` | les `docker compose` correspondants |
| `make shell` | `docker compose exec backend /bin/sh` (`S=frontend` pour l'autre) |
| `make logs S=backend` | logs d'un seul service ; sans `S`, les deux |
| `make backup` | archive les bases SQLite du volume dans `deploy/backups/` |

L'interface est ensuite accessible via Traefik sur `https://<APP_HOST>/`
(ex. `https://loreplexum.sternum-lab.duckdns.org/`), sans port à ouvrir sur l'hôte.
L'API répond sur `https://<APP_HOST>/api/v1/health` et sa documentation
interactive sur `https://<APP_HOST>/api/docs`.
Le certificat est le wildcard Let's Encrypt `*.sternum-lab.duckdns.org` émis par
Traefik (résolveur `duckdns`, challenge DNS-01) : rien à faire côté application.

> Traefik lit les labels **des conteneurs en cours d'exécution**, pas du fichier
> compose sur disque. Après modification des labels, `docker compose up -d
> --force-recreate` (un simple `restart` ne suffit pas).

> Besoin d'un accès direct pour déboguer (hors Traefik) ? Ajoutez temporairement
> `ports: ["8000:8000"]` au service `backend` (ou `["8080:80"]` au `frontend`)
> dans `docker-compose.yml`.

> **Page blanche après un déploiement ?** C'est presque toujours un `index.html`
> mis en cache qui pointe vers des assets disparus. `nginx.conf` sert `index.html`
> en `no-store` précisément pour l'éviter ; si le problème persiste, videz le
> cache du navigateur et vérifiez qu'aucun proxy intermédiaire ne le remet.

## 4. Mise à jour

```bash
cd deploy
make deploy                   # git pull + check + up -d --build
```

Le volume `tnfc-data` (bases SQLite) et les fichiers sur auditus survivent aux
reconstructions.

> **Migrations à faire une fois** sur un `deploy/app.env` existant — `make check`
> refuse de déployer tant qu'elles manquent :
>
> - `KEYBINDS_DB_PATH=/data/keybinds.db` (carte des touches) ;
> - `CONFIG_ENV_PATH=/data/app.env` (refactor backend/frontend). Sans cette ligne,
>   la page Paramètres écrit **dans la couche d'image** et les chemins saisis
>   depuis l'interface sont perdus à la reconstruction suivante.
>
> Dans les deux cas, le fichier est sinon créé dans l'image (`/app/data`) et repart
> de zéro à chaque `--build`.

> **Reconstruction complète requise** au passage à cette version : le service
> `tnfc` est remplacé par `backend` + `frontend`. Faites `make down` puis
> `make up` — `docker compose` ne supprime pas l'ancien conteneur tout seul si son
> nom de service a disparu. Le volume `tnfc-data` est conservé.

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
