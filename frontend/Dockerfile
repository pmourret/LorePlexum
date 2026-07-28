# Image du frontend LorePlexum : SPA React construite, servie par nginx.
#
# Build multi-étapes : Node ne sert qu'à produire `dist/`, il n'est pas dans
# l'image finale. Le résultat est ~15 Mo de fichiers statiques, sans runtime JS.
#
# Contexte de build attendu : le dossier `frontend/`.

# --- Étape 1 : construction ----------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /build

# Couche de dépendances séparée : tant que package-lock.json ne bouge pas, le
# `npm ci` est servi par le cache.
COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.ts index.html ./
COPY src/ ./src/

# `npm run build` lance `tsc -b` avant Vite : une erreur de typage casse le build
# plutôt que de produire un bundle silencieusement faux.
RUN npm run build

# --- Étape 2 : service ---------------------------------------------------------
FROM nginx:1.27-alpine

COPY --from=build /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
