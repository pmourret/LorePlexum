# Déploiement de LorePlexum sur le serveur Docker « hiatus ».
#
# Enveloppe les commandes de DEPLOYMENT.md, qui reste la référence : ce fichier
# n'ajoute aucune étape, il évite juste de les retaper et ajoute un pré-vol
# (`make check`) qui vérifie les prérequis silencieux — montage CIFS, réseau
# Traefik, variables d'environnement — au lieu de les découvrir dans les logs.
#
# Vit dans `deploy/` et non à la racine : toutes les commandes s'exécutent ainsi
# depuis le dossier du compose, exactement comme la documentation les décrit, et
# Docker Compose y trouve `.env` sans ambiguïté de répertoire de projet.
#
# Usage : cd deploy && make <cible>   (make seul affiche l'aide)

COMPOSE   := docker compose
# Deux services depuis le refactor backend/frontend. `S` permet d'en cibler un :
#   make logs S=frontend   make shell S=backend   make restart S=backend
S         ?=
BACKEND   := backend
CONTAINER := loreplexum-backend
MOUNT     := /mnt/TakeNotes
NETWORK   := proxy
STAMP     := $(shell date +%Y%m%d-%H%M%S)

.DEFAULT_GOAL := help
.PHONY: help init check build up deploy recreate down restart logs ps shell backup

help: ## Affiche cette aide
	@echo "LorePlexum — déploiement (hiatus)"
	@echo
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
	@echo

# --- Configuration -------------------------------------------------------------

init: ## Crée .env et app.env depuis les .example (n'écrase jamais l'existant)
	@for f in .env app.env; do \
		if [ -f "$$f" ]; then \
			echo "  = $$f existe déjà, laissé intact"; \
		else \
			cp "$$f.example" "$$f" && echo "  + $$f créé depuis $$f.example"; \
		fi; \
	done
	@echo
	@echo "Éditez maintenant .env (APP_HOST) et app.env (chemins), puis : make check"

check: ## Vérifie les prérequis avant déploiement (montage, réseau, variables)
	@ok=0; \
	for f in .env app.env; do \
		[ -f "$$f" ] || { echo "  ✗ $$f manquant — lancez 'make init'"; ok=1; }; \
	done; \
	if [ -f .env ]; then \
		grep -q '^APP_HOST=.\+' .env \
			&& echo "  ✓ APP_HOST = $$(grep '^APP_HOST=' .env | cut -d= -f2-)" \
			|| { echo "  ✗ APP_HOST vide dans .env"; ok=1; }; \
	fi; \
	if [ -f app.env ]; then \
		for v in FULL_CONTEXT_JSON_PATH ENTRIES_DIR TAKE_NOTES_EXPORT_DIR; do \
			grep -q "^$$v=.\+" app.env || { echo "  ✗ $$v vide dans app.env"; ok=1; }; \
		done; \
		for v in DATABASE_PATH KEYBINDS_DB_PATH CONFIG_ENV_PATH; do \
			grep -q "^$$v=/data/" app.env \
				|| { echo "  ✗ $$v absent ou hors de /data dans app.env :"; \
				     echo "      le fichier serait créé dans l'image et perdu au prochain build"; ok=1; }; \
		done; \
	fi; \
	mountpoint -q $(MOUNT) 2>/dev/null \
		&& echo "  ✓ $(MOUNT) monté" \
		|| { echo "  ✗ $(MOUNT) non monté — 'sudo mount $(MOUNT)' (voir DEPLOYMENT.md)"; ok=1; }; \
	docker network inspect $(NETWORK) >/dev/null 2>&1 \
		&& echo "  ✓ réseau '$(NETWORK)' présent" \
		|| { echo "  ✗ réseau '$(NETWORK)' absent — 'docker network create $(NETWORK)'"; ok=1; }; \
	echo; \
	echo "  ! Aucune authentification applicative : vérifiez que l'accès est"; \
	echo "    restreint au niveau réseau (allowlist IP Traefik, VPN) avant toute"; \
	echo "    exposition publique — /api/v1/settings écrit des chemins disque."; \
	echo; \
	[ $$ok -eq 0 ] && echo "Prêt pour 'make up'." || { echo "Corrigez les points ci-dessus."; exit 1; }

# --- Cycle de vie --------------------------------------------------------------

build: ## Reconstruit les images sans démarrer
	$(COMPOSE) build

up: check ## Démarre (ou met à jour) la stack après reconstruction
	$(COMPOSE) up -d --build
	@echo
	@host=$$(grep '^APP_HOST=' .env | cut -d= -f2-); \
	 echo "  SPA : https://$$host/"; \
	 echo "  API : https://$$host/api/v1/health"; \
	 echo "  Doc : https://$$host/api/docs"

deploy: ## Met à jour depuis git puis redéploie (flux de mise à jour nominal)
	git pull
	@$(MAKE) up

recreate: ## Recrée les conteneurs de force — requis après un changement de label Traefik
	$(COMPOSE) up -d --build --force-recreate

down: ## Arrête et supprime les conteneurs (le volume de données est conservé)
	$(COMPOSE) down

restart: ## Redémarre les services sans reconstruire (S=backend pour un seul)
	$(COMPOSE) restart $(S)

# --- Exploitation --------------------------------------------------------------

logs: ## Suit les logs des deux services (S=backend pour n'en suivre qu'un)
	$(COMPOSE) logs -f $(S)

ps: ## État des conteneurs
	$(COMPOSE) ps

shell: ## Ouvre un shell dans le backend (S=frontend pour l'autre)
	$(COMPOSE) exec $(if $(S),$(S),$(BACKEND)) /bin/sh

backup: ## Archive les bases SQLite du volume dans ./backups/
	@docker container inspect $(CONTAINER) >/dev/null 2>&1 \
		|| { echo "Conteneur $(CONTAINER) introuvable — déployez d'abord."; exit 1; }
	@mkdir -p backups
	@docker run --rm --volumes-from $(CONTAINER) \
		-v "$(CURDIR)/backups:/backup" alpine \
		tar czf /backup/data-$(STAMP).tar.gz -C /data .
	@echo "  → backups/data-$(STAMP).tar.gz"
