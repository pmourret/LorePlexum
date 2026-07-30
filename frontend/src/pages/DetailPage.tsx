import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import { useInjection } from '../api/hooks'
import { Alert, Loading, QueryError } from '../components/ui'

export default function DetailPage() {
  const { id } = useParams()
  const injectionId = Number(id)
  const injection = useInjection(injectionId)

  const back = (
    <p className="back-link">
      <Link className="btn small" to="/history">
        <span aria-hidden="true">←</span> Retour à l'historique
      </Link>
    </p>
  )

  if (!Number.isFinite(injectionId)) {
    return (
      <>
        {back}
        <Alert level="error">Identifiant d'injection invalide.</Alert>
      </>
    )
  }

  if (injection.isPending)
    return (
      <>
        {back}
        <Loading label={`Chargement de l'injection #${injectionId}…`} />
      </>
    )

  if (injection.error) {
    const notFound = injection.error instanceof ApiError && injection.error.status === 404
    return (
      <>
        {back}
        {notFound ? (
          <Alert level="error">Injection introuvable.</Alert>
        ) : (
          <QueryError error={injection.error} />
        )}
      </>
    )
  }

  const item = injection.data
  // `metadata` a un défaut côté Pydantic, donc optionnel dans le schéma généré.
  const metadata = item.metadata ?? {}
  const hasMetadata = Object.keys(metadata).length > 0

  return (
    <>
      {back}
      <h1>Injection #{item.id}</h1>

      {/* `<dl>` et non des `<div>` : ce bloc est une liste d'étiquettes et de
          valeurs. En `<div>`/`<span>`, rien ne liait « Arc » à sa valeur — lue à
          voix haute, la carte donnait six libellés puis six valeurs en vrac. */}
      <dl className="card meta-grid">
        <Meta label="Date d'injection" value={item.date_injection} />
        <Meta
          label="Catégorie"
          value={item.categorie ? <span className="tag">{item.categorie}</span> : null}
        />
        <Meta label="Arc" value={item.arc} />
        <Meta label="N° d'entrée" value={item.entry_number ? `#${item.entry_number}` : null} />
        <Meta label="Date de session" value={item.date_session} />
        <Meta label="Fichier XML" value={item.xml_file} />
      </dl>

      {item.has_pdf && (
        <p className="detail-actions">
          {/* Téléchargement : un vrai lien, pas une navigation du routeur. */}
          <a className="btn small" href={api.pdfUrl(item.id)} download>
            <span aria-hidden="true">📄</span> Télécharger le PDF
          </a>
          <span className="muted">{item.pdf_path}</span>
        </p>
      )}

      {item.resume && (
        <>
          <h2>Résumé</h2>
          <div className="card text-block">{item.resume}</div>
        </>
      )}

      <h2>Texte injecté</h2>
      <div className="card text-block">{item.texte}</div>

      {hasMetadata && (
        <>
          <h2>Métadonnées</h2>
          {/* `tabIndex` : le bloc défile horizontalement sur un JSON large, ce qui
              est inatteignable sans souris tant qu'il n'est pas focalisable. */}
          <pre className="card code" tabIndex={0} role="region" aria-label="Métadonnées (JSON)">
            {JSON.stringify(metadata, null, 2)}
          </pre>
        </>
      )}
    </>
  )
}

/**
 * Une paire étiquette / valeur de la carte d'en-tête.
 *
 * Le `<div>` intermédiaire est ce qui fait de la paire une seule cellule de grille :
 * un `<dt>` et un `<dd>` posés directement dans la grille occuperaient deux cases,
 * et les colonnes se désaligneraient dès qu'une valeur passe sur deux lignes.
 */
function Meta({ label, value }: { label: string; value: ReactNode }) {
  const empty = value === null || value === undefined || value === ''
  return (
    <div>
      <dt className="k">{label}</dt>
      <dd className={empty ? 'muted' : undefined}>{empty ? '—' : value}</dd>
    </div>
  )
}
