import { Link, useParams } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import { useInjection } from '../api/hooks'
import { Alert, Loading, QueryError } from '../components/ui'

export default function DetailPage() {
  const { id } = useParams()
  const injectionId = Number(id)
  const injection = useInjection(injectionId)

  const back = (
    <p>
      <Link className="btn small" to="/history">
        ← Retour à l'historique
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

  if (injection.isPending) return <>{back}<Loading /></>

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

      <div className="card meta-grid">
        <div>
          <span className="k">Date d'injection</span>
          {item.date_injection}
        </div>
        <div>
          <span className="k">Catégorie</span>
          <span className="tag">{item.categorie}</span>
        </div>
        <div>
          <span className="k">Arc</span>
          {item.arc}
        </div>
        <div>
          <span className="k">N° d'entrée</span>#{item.entry_number}
        </div>
        <div>
          <span className="k">Date de session</span>
          {item.date_session}
        </div>
        <div>
          <span className="k">Fichier XML</span>
          {item.xml_file}
        </div>
      </div>

      {item.has_pdf && (
        <p>
          {/* Téléchargement : un vrai lien, pas une navigation du routeur. */}
          <a className="btn small" href={api.pdfUrl(item.id)} download>
            📄 Télécharger le PDF
          </a>{' '}
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
          <pre className="card code">{JSON.stringify(metadata, null, 2)}</pre>
        </>
      )}
    </>
  )
}
