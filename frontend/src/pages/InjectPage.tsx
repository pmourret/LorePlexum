import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  ApiError,
  api,
  type GameDate,
  type InjectionCreate,
  type InjectionResult,
} from '../api/client'
import {
  useArcs,
  useCalendar,
  useCategories,
  useCreateInjection,
  useHealth,
  useMetadataFiles,
  useSuggestedDate,
} from '../api/hooks'
import DateField from '../components/DateField'
import { Alert, ExecutionLog, Loading, QueryError } from '../components/ui'

export default function InjectPage() {
  const health = useHealth()
  const configured = Boolean(health.data?.config_ok)

  const categories = useCategories()
  const calendar = useCalendar()
  const arcs = useArcs(configured)
  const metadataFiles = useMetadataFiles(configured)

  const [category, setCategory] = useState('')
  const [resume, setResume] = useState('')
  const [text, setText] = useState('')
  const [arcSelect, setArcSelect] = useState('')
  const [newArc, setNewArc] = useState('')
  const [metadataFile, setMetadataFile] = useState('')
  const [metadataJson, setMetadataJson] = useState('')
  const [date, setDate] = useState<GameDate | null>(null)
  const [metadataError, setMetadataError] = useState<string | null>(null)

  // Première catégorie sélectionnée par défaut, comme l'ancien formulaire.
  useEffect(() => {
    if (!category && categories.data?.length) setCategory(categories.data[0].key)
  }, [categories.data, category])

  // La date suggérée suit la catégorie ; l'utilisateur reste libre de la changer
  // ensuite, sa saisie n'est pas écrasée tant qu'il ne change pas de catégorie.
  const suggested = useSuggestedDate(category, configured)
  useEffect(() => {
    if (suggested.data) setDate(suggested.data.date)
  }, [suggested.data])
  useEffect(() => {
    if (!suggested.data && calendar.data && !date) setDate(calendar.data.default)
  }, [calendar.data, suggested.data, date])

  const create = useCreateInjection()

  // Le doublon arrive en 409 : le corps porte le journal et l'injection existante.
  const duplicate =
    create.error instanceof ApiError && create.error.isDuplicate
      ? (create.error.body as InjectionResult)
      : null
  // Un échec de pipeline (500) porte lui aussi un corps complet, qu'on veut afficher.
  const failure =
    create.error instanceof ApiError && create.error.status === 500
      ? (create.error.body as InjectionResult)
      : null
  const result = create.data ?? duplicate ?? failure

  async function buildPayload(allowDuplicate: boolean): Promise<InjectionCreate | null> {
    setMetadataError(null)

    // Métadonnées : fichier choisi prioritaire, sinon JSON collé, sinon {}.
    let metadata: Record<string, unknown> = {}
    if (metadataFile) {
      try {
        metadata = await api.metadataFile(metadataFile)
      } catch (error) {
        setMetadataError(
          error instanceof Error ? error.message : 'Métadonnées illisibles.',
        )
        return null
      }
    } else if (metadataJson.trim()) {
      try {
        const parsed = JSON.parse(metadataJson)
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
          setMetadataError('Les métadonnées doivent être un objet JSON.')
          return null
        }
        metadata = parsed
      } catch (error) {
        setMetadataError(
          `JSON de métadonnées invalide : ${error instanceof Error ? error.message : error}`,
        )
        return null
      }
    }

    return {
      category,
      resume,
      text,
      metadata,
      arc: newArc.trim() || arcSelect || null,
      entry_date: date,
      allow_duplicate: allowDuplicate,
      generate_pdf: true,
    }
  }

  async function submit(allowDuplicate: boolean) {
    const payload = await buildPayload(allowDuplicate)
    if (payload) create.mutate(payload)
  }

  if (categories.isPending || calendar.isPending) return <Loading />

  return (
    <>
      <h1>Nouvelle injection</h1>

      <div className="grid">
        <form
          className="card"
          onSubmit={(event) => {
            event.preventDefault()
            void submit(false)
          }}
        >
          <label>
            Catégorie
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              {categories.data?.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.key}
                </option>
              ))}
            </select>
          </label>

          <label>
            Résumé <span className="muted">(facultatif)</span>
            <textarea
              rows={3}
              value={resume}
              placeholder="Bref résumé de l'entrée, une ou deux phrases…"
              onChange={(event) => setResume(event.target.value)}
            />
          </label>

          <label>
            Texte du journal <span className="req">*</span>
            <textarea
              rows={12}
              value={text}
              placeholder="Corps complet du journal enrichi…"
              onChange={(event) => setText(event.target.value)}
            />
            <small>Colle directement le texte : aucune balise à ajouter.</small>
          </label>

          <div className="row">
            <label>
              Arc existant
              <select
                value={arcSelect}
                onChange={(event) => setArcSelect(event.target.value)}
                disabled={Boolean(newArc.trim())}
              >
                <option value="">— nouvel arc (auto) —</option>
                {arcs.data?.map((arc) => (
                  <option key={arc} value={arc}>
                    {arc}
                  </option>
                ))}
              </select>
            </label>
            <label>
              …ou nom d'un nouvel arc
              <input
                type="text"
                value={newArc}
                placeholder="ex. arc_prologue"
                onChange={(event) => setNewArc(event.target.value)}
              />
            </label>
          </div>

          {calendar.data && date && (
            <DateField calendar={calendar.data} value={date} onChange={setDate} />
          )}

          <details className="optional-block">
            <summary>Métadonnées (facultatif — hérité de la V1)</summary>
            <small className="muted">
              Vestige du workflow ChatGPT. Optionnel : laisser vide pour ne rien joindre.
            </small>
            <div className="row">
              <label>
                Métadonnées (fichier)
                <select
                  value={metadataFile}
                  onChange={(event) => setMetadataFile(event.target.value)}
                >
                  <option value="">— aucune / JSON ci-dessous —</option>
                  {metadataFiles.data?.map((file) => (
                    <option key={file} value={file}>
                      {file}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              …ou métadonnées JSON collées
              <textarea
                rows={3}
                value={metadataJson}
                disabled={Boolean(metadataFile)}
                placeholder='{"lieu": "Bordeciel", "emotion": "tension"}'
                onChange={(event) => setMetadataJson(event.target.value)}
              />
            </label>
          </details>

          <button
            type="submit"
            className="btn primary"
            disabled={!configured || create.isPending || !text.trim()}
          >
            Injecter
            {create.isPending && <span className="spinner" />}
          </button>
        </form>

        <div className="card result-panel">
          <h2>Résultat</h2>

          {metadataError && <Alert level="error">{metadataError}</Alert>}

          {!result && !create.error && !metadataError && (
            <p className="muted">Le journal d'exécution s'affichera ici après l'injection.</p>
          )}

          {/* Erreur sans corps structuré : réseau, 503, 422 de validation. */}
          {create.error && !result && <QueryError error={create.error} />}

          {create.isSuccess && create.data && (
            <>
              <Alert level="success">
                Injection réussie — catégorie <strong>{create.data.category}</strong>, arc{' '}
                <strong>{create.data.arc}</strong>, entrée{' '}
                <strong>#{create.data.entry_number}</strong>
                {create.data.injection_id && (
                  <span className="muted"> (archive #{create.data.injection_id})</span>
                )}
              </Alert>
              {create.data.has_pdf && create.data.injection_id && (
                <p>
                  <a
                    className="btn small"
                    href={api.pdfUrl(create.data.injection_id)}
                    download
                  >
                    📄 Télécharger le PDF
                  </a>
                </p>
              )}
            </>
          )}

          {duplicate?.duplicate && (
            <>
              <Alert level="warning">
                <strong>Doublon détecté.</strong> Ce texte a déjà été injecté le{' '}
                {duplicate.duplicate.date_injection} (catégorie «{' '}
                {duplicate.duplicate.categorie} », arc « {duplicate.duplicate.arc} », entrée #
                {duplicate.duplicate.entry_number}).
              </Alert>
              <div className="editor-actions">
                <button
                  type="button"
                  className="btn danger"
                  disabled={create.isPending}
                  onClick={() => void submit(true)}
                >
                  Injecter malgré tout
                </button>
                <Link className="btn small" to={`/injection/${duplicate.duplicate.id}`}>
                  Voir l'injection existante
                </Link>
              </div>
            </>
          )}

          {failure && <Alert level="error">L'injection a échoué. Voir le journal ci-dessous.</Alert>}

          {result && <ExecutionLog messages={result.messages} />}
        </div>
      </div>
    </>
  )
}
