import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useFacets, useInjections } from '../api/hooks'
import { Loading, QueryError } from '../components/ui'

const PER_PAGE = 20

/**
 * Les filtres vivent dans l'URL (`?categorie=&arc=&search=&page=`).
 *
 * C'est le comportement que l'ancienne page avait naturellement et qu'une SPA
 * perd si on n'y prend pas garde : un historique filtré reste partageable, et
 * le bouton « précédent » du navigateur fait ce qu'on attend.
 */
export default function HistoryPage() {
  const [params, setParams] = useSearchParams()

  const categorie = params.get('categorie') ?? ''
  const arc = params.get('arc') ?? ''
  const search = params.get('search') ?? ''
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)

  // La recherche est débouncée : on ne repart pas au serveur à chaque frappe.
  const [searchDraft, setSearchDraft] = useState(search)
  useEffect(() => setSearchDraft(search), [search])
  useEffect(() => {
    if (searchDraft === search) return
    const timer = setTimeout(() => update({ search: searchDraft, page: '1' }), 350)
    return () => clearTimeout(timer)
  }, [searchDraft]) // eslint-disable-line react-hooks/exhaustive-deps

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next, { replace: true })
  }

  const facets = useFacets()
  const injections = useInjections({
    categorie: categorie || undefined,
    arc: arc || undefined,
    search: search || undefined,
    page,
    per_page: PER_PAGE,
  })

  const filtered = Boolean(categorie || arc || search)

  return (
    <>
      <h1>Historique des injections</h1>

      <form className="filters card" onSubmit={(event) => event.preventDefault()}>
        <label>
          Catégorie
          <select
            value={categorie}
            onChange={(event) => update({ categorie: event.target.value, page: '1' })}
          >
            <option value="">Toutes</option>
            {facets.data?.categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Arc
          <select value={arc} onChange={(event) => update({ arc: event.target.value, page: '1' })}>
            <option value="">Tous</option>
            {facets.data?.arcs.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label className="grow">
          Recherche
          <input
            type="text"
            value={searchDraft}
            placeholder="texte ou résumé…"
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </label>
      </form>

      {injections.isPending && <Loading />}
      {injections.error && <QueryError error={injections.error} />}

      {injections.data && (
        <div className={injections.isFetching ? 'stale' : undefined}>
          <p className="muted count">
            {injections.data.total} injection(s){filtered && ' (filtré)'}
          </p>

          {injections.data.items.length === 0 ? (
            <p className="muted empty">
              Aucune injection enregistrée{filtered && ' pour ces filtres'}.
            </p>
          ) : (
            <>
              <table className="table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Date d'injection</th>
                    <th>Catégorie</th>
                    <th>Arc</th>
                    <th>Entrée</th>
                    <th>Date session</th>
                    <th>Résumé</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {injections.data.items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.id}</td>
                      <td className="nowrap">{item.date_injection}</td>
                      <td>
                        <span className="tag">{item.categorie}</span>
                      </td>
                      <td>{item.arc}</td>
                      <td>#{item.entry_number}</td>
                      <td className="nowrap">{item.date_session}</td>
                      <td className="ellipsis">{item.resume}</td>
                      <td>
                        <Link className="btn small" to={`/injection/${item.id}`}>
                          Détail
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {injections.data.total_pages > 1 && (
                <div className="pager">
                  <button
                    type="button"
                    className="btn small"
                    disabled={page <= 1}
                    onClick={() => update({ page: String(page - 1) })}
                  >
                    ← Précédent
                  </button>
                  <span className="muted">
                    Page {page} / {injections.data.total_pages}
                  </span>
                  <button
                    type="button"
                    className="btn small"
                    disabled={page >= injections.data.total_pages}
                    onClick={() => update({ page: String(page + 1) })}
                  >
                    Suivant →
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </>
  )
}
