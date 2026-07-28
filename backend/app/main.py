"""Point d'entrée ASGI — API JSON `/api/v1`, et l'UI HTMX tant qu'elle vit.

Phase 1 du refactor backend/frontend : l'API est complète et l'ancienne interface
HTMX continue de tourner sur la même application. Elle est montée via un drapeau
(`legacy_ui`) précisément pour que son retrait, une fois la SPA React en place, soit
une seule ligne à supprimer et non une chirurgie.

La documentation vit sous `/api/docs` : en production, Traefik route `/api` vers ce
service et tout le reste vers le frontend, donc `/docs` à la racine appartiendrait
à la SPA.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.config import get_deployment_settings
from backend.app.deps import ConfigurationError
from backend.app.routers import context, injections, keybinds, settings

API_PREFIX = "/api/v1"


def create_app(*, legacy_ui: bool = True) -> FastAPI:
    app = FastAPI(
        title="LorePlexum — TNFCDataInjector",
        description=(
            "Réinjection de journaux Skyrim enrichis dans le JSON de contexte "
            "narratif et les exports XML TakeNotes."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    for router in (context.router, injections.router, keybinds.router, settings.router):
        app.include_router(router, prefix=API_PREFIX)

    @app.exception_handler(ConfigurationError)
    def _configuration_error(request: Request, exc: ConfigurationError) -> JSONResponse:
        """Config applicative invalide -> 503, pas 500.

        Le service fonctionne ; c'est son environnement qui ne va pas. La distinction
        compte pour le client, qui doit renvoyer l'utilisateur vers les Paramètres
        plutôt qu'afficher une erreur interne.
        """
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc), "code": "configuration_invalid"},
        )

    # --- Origine de développement (CORS) ---------------------------------------
    # En production il n'y en a pas : Traefik sert l'API et la SPA sur le même host,
    # donc en same-origin. Ce bloc n'existe que pour le cas où l'on ferait tourner
    # Vite sans son proxy ; `DEV_CORS_ORIGIN` est vide par défaut.
    dev_origin = get_deployment_settings().dev_cors_origin
    if dev_origin:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=[dev_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if legacy_ui:
        from webapp.ui import mount_legacy_ui

        mount_legacy_ui(app)

    return app


app = create_app()
