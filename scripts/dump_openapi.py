"""Écrit le schéma OpenAPI du backend dans un fichier, sans démarrer de serveur.

Sert à régénérer le client TypeScript du frontend :

    cd frontend && npm run generate:api

Le contrat d'API n'est donc jamais écrit à la main des deux côtés : les schémas
Pydantic de `backend/app/schemas/` en sont la source unique.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import create_app  # noqa: E402


def main() -> int:
    destination = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"

    schema = create_app().openapi()

    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"OpenAPI écrit dans {destination} ({len(schema.get('paths', {}))} routes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
