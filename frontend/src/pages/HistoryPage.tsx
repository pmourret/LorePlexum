import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useFacets, useInjections } from '../api/hooks'
import { Loading, QueryError } from '../components/ui'

const PER_PAGE = 20

/**
 * Valeur absente rendue en tiret cadratin.
 *
 * `categorie`, `arc`, `entry_number` et `date_session` sont tous facultatifs côté
 * schéma. Rendus bruts, un arc manquant donnait une cellule vide (indiscernable
 * d'un défaut d'affichage) et un numéro d'entrée manquant un « # » solitaire.
 */
function Value({ children, prefix = '' }: { children: unknown; prefix?: string }) {
  if (children === null || children === undefined || children === '') {
    return <span className="muted">—</span>
  }
  return (
    <>
      {prefix}
      {String(children)}
    </>
  )
}

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

  /** Le brouillon diffère de la valeur appliquée : le débounce court encore. */
  const pendingSearch = searchDraft !== search

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next, { replace: true })
  }

  function clearFilters() {
    setSearchDraft('')
    update({ categorie: '', arc: '', search: '', page: '' })
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
          {/* Le débounce de 350 ms se voyait nulle part : entre la frappe et le
              résultat, rien ne disait que la requête allait partir. La classe
              `.searching` du thème n'était utilisée par personne. */}
          {pendingSearch && (
            <span className="field-hint searching">
              <span className="spinner on-dark" aria-hidden="true" />
              recherche…
            </span>
          )}
          <input
            type="search"
            value={searchDraft}
            placeholder="texte ou résumé…"
            onChange={(event) => setSearchDraft(event.target.value)}
          />
        </label>
        {filtered && (
          <button type="button" className="btn small" onClick={clearFilters}>
            Effacer les filtres
          </button>
        )}
      </form>

      {injections.isPending && <Loading label="Chargement de l'historique…" />}
      {injections.error && <QueryError error={injections.error} />}

      {injections.data && (
        // `aria-busy` double l'estompage : une opacité réduite ne s'entend pas, et
        // sans elle un lecteur d'écran lisait des lignes déjà périmées comme si
        // elles étaient à jour.
        <div
          className={injections.isFetching ? 'stale' : undefined}
          aria-busy={injections.isFetching}
        >
          {/* Le total change au fil du filtrage : `role="status"` le fait annoncer
              sans interrompre la saisie en cours. */}
          <p className="muted count" role="status">
            {injections.data.total} injection(s){filtered && ' (filtré)'}
          </p>

          {injections.data.items.length === 0 ? (
            <div className="muted empty-state">
              <p>Aucune injection enregistrée{filtered && ' pour ces filtres'}.</p>
              {filtered && (
                <button type="button" className="btn small" onClick={clearFilters}>
                  Effacer les filtres
                </button>
              )}
            </div>
          ) : (
            <>
              {/* Huit colonnes ne tiennent pas sous ~900 px. Le tableau défile dans
                  son cadre au lieu d'élargir la page. `tabIndex` : sans lui, la zone
                  de défilement est inatteignable au clavier. */}
              <div
                className="table-wrap"
                tabIndex={0}
                role="region"
                aria-label="Liste des injections"
              >
                <table className="table">
                  <caption className="sr-only">
                    Injections enregistrées, page {page} sur {injections.data.total_pages}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Date d'injection</th>
                      <th scope="col">Catégorie</th>
                      <th scope="col">Arc</th>
                      <th scope="col">Entrée</th>
                      <th scope="col">Date session</th>
                      <th scope="col">Résumé</th>
                      {/* Une cellule d'en-tête vide laisse la colonne d'actions sans
                          nom : à l'oreille, « Détail » arrive sans savoir de quoi. */}
                      <th scope="col">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {injections.data.items.map((item) => (
                      <tr key={item.id}>
                        {/* L'identifiant nomme la ligne : `row` plutôt qu'une cellule
                            de données, pour que chaque cellule s'annonce avec lui. */}
                        <th scope="row">{item.id}</th>
                        <td className="nowrap">{item.date_injection}</td>
                        <td>
                          {item.categorie ? (
                            <span className="tag">{item.categorie}</span>
                          ) : (
                            <Value>{null}</Value>
                          )}
                        </td>
                        <td>
                          <Value>{item.arc}</Value>
                        </td>
                        <td>
                          <Value prefix="#">{item.entry_number}</Value>
                        </td>
                        <td className="nowrap">
                          <Value>{item.date_session}</Value>
                        </td>
                        {/* `title` : le résumé est tronqué à 280 px, sans lui le texte
                            coupé n'était consultable nulle part. */}
                        <td className="ellipsis" title={item.resume ?? undefined}>
                          <Value>{item.resume}</Value>
                        </td>
                        <td>
                          <Link
                            className="btn small"
                            to={`/injection/${item.id}`}
                            aria-label={`Détail de l'injection ${item.id}`}
                          >
                            Détail
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {injections.data.total_pages > 1 && (
                <nav className="pager" aria-label="Pagination de l'historique">
                  <button
                    type="button"
                    className="btn small"
                    disabled={page <= 1}
                    onClick={() => update({ page: String(page - 1) })}
                  >
                    <span aria-hidden="true">←</span> Précédent
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
                    Suivant <span aria-hidden="true">→</span>
                  </button>
                </nav>
              )}
            </>
          )}
        </div>
      )}
    </>
  )
}
