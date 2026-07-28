"""Pipeline d'injection et historique archivé."""

import os

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse

from backend.app.deps import Db, ReporterDep, Service
from backend.app.schemas.injections import (
    InjectionCreate,
    InjectionDetail,
    InjectionFacets,
    InjectionPage,
    InjectionResultOut,
    InjectionSummary,
)
from backend.core.injection_service import XML_FILES_MAPPING, InjectionRequest

router = APIRouter(tags=["injections"])


@router.post(
    "/injections",
    response_model=InjectionResultOut,
    status_code=201,
    summary="Exécute le pipeline d'injection JSON -> XML -> PDF",
    responses={
        409: {"description": "Texte déjà injecté ; rejouer avec allow_duplicate=true"},
        500: {"description": "Le pipeline a échoué ; voir `messages`"},
        503: {"description": "Configuration applicative invalide"},
    },
)
def create_injection(
    payload: InjectionCreate,
    response: Response,
    service: Service,
    reporter: ReporterDep,
) -> InjectionResultOut:
    """Lance une injection.

    Le corps de réponse a la **même forme** dans les trois cas (succès, doublon,
    échec) : seul le code de statut change. Le journal d'exécution est toujours
    présent, car c'est lui qui explique ce qui s'est passé.
    """
    if payload.category not in XML_FILES_MAPPING:
        raise HTTPException(
            status_code=422,
            detail=f"Catégorie inconnue : {payload.category}. "
                   f"Attendu : {', '.join(XML_FILES_MAPPING)}.",
        )

    result = service.run(InjectionRequest(
        category=payload.category,
        resume=payload.resume,
        text=payload.text,
        metadata=payload.metadata,
        arc=payload.arc or None,
        entry_date=payload.entry_date.to_stored_string() if payload.entry_date else None,
        max_tokens=payload.max_tokens,
        generate_pdf=payload.generate_pdf,
        allow_duplicate=payload.allow_duplicate,
    ))

    out = InjectionResultOut(
        success=result.success,
        messages=result.messages,
        entry_number=result.entry_number,
        arc=result.arc,
        category=result.category,
        xml_file=result.xml_file,
        injection_id=result.injection_id,
        has_pdf=bool(result.pdf_path),
        duplicate=InjectionSummary.from_row(result.duplicate) if result.duplicate else None,
    )

    if result.duplicate:
        response.status_code = 409
    elif not result.success:
        response.status_code = 500
    return out


@router.get("/injections", response_model=InjectionPage, summary="Historique filtré")
def list_injections(
    db: Db,
    categorie: str = "",
    arc: str = "",
    search: str = "",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> InjectionPage:
    filters = {
        "categorie": categorie or None,
        "arc": arc or None,
        "search": search or None,
    }
    rows = db.list_injections(limit=per_page, offset=(page - 1) * per_page, **filters)
    total = db.count(**filters)
    return InjectionPage(
        items=[InjectionSummary.from_row(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total + per_page - 1) // per_page),
    )


# Déclaré AVANT /injections/{injection_id} : sinon « facets » serait interprété
# comme un identifiant et rejeté en 422.
@router.get("/injections/facets", response_model=InjectionFacets,
            summary="Valeurs disponibles pour les filtres")
def injection_facets(db: Db) -> InjectionFacets:
    return InjectionFacets(
        categories=list(XML_FILES_MAPPING.keys()),
        arcs=db.distinct_arcs(),
    )


@router.get("/injections/{injection_id}", response_model=InjectionDetail,
            responses={404: {"description": "Injection inconnue"}})
def get_injection(injection_id: int, db: Db) -> InjectionDetail:
    row = db.get_injection(injection_id)
    if not row:
        raise HTTPException(status_code=404, detail="Injection introuvable.")
    return InjectionDetail.from_row(row)


@router.get("/injections/{injection_id}/pdf", response_class=FileResponse,
            summary="Télécharge le PDF archivé",
            responses={404: {"description": "Aucun PDF disponible"}})
def download_pdf(injection_id: int, db: Db) -> FileResponse:
    row = db.get_injection(injection_id)
    if not row:
        raise HTTPException(status_code=404, detail="Injection introuvable.")

    pdf_path = row.get("pdf_path")
    # Le PDF est généré sur un partage réseau : il peut avoir disparu depuis
    # l'archivage. On distingue « jamais généré » de « plus sur le disque ».
    if not pdf_path:
        raise HTTPException(status_code=404, detail="Aucun PDF n'a été généré pour cette injection.")
    if not os.path.isfile(pdf_path):
        raise HTTPException(
            status_code=404,
            detail="Le PDF archivé n'est plus présent sur le disque.",
        )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=os.path.basename(pdf_path),
    )
