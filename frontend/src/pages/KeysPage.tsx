import { useEffect, useMemo, useRef, useState } from 'react'

import { api, type Key, type KeyBind, type KeyCategory, type Keymap } from '../api/client'
import { useClearKeybind, useKeymap, useSetKeybind } from '../api/hooks'
import { Loading, QueryError } from '../components/ui'

/**
 * Carte des touches.
 *
 * `GET /api/v1/keymap` renvoie tout l'état en un appel : disposition, familles,
 * assignations, compteurs. Filtrer par famille ou chercher une action devient
 * donc instantané et purement local — l'ancienne interface rechargeait le
 * clavier entier au serveur à chaque édition, et ne pouvait pas filtrer du tout.
 */
export default function KeysPage() {
  const keymap = useKeymap()
  const [editing, setEditing] = useState<number | null>(null)
  const [filterCat, setFilterCat] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  if (keymap.isPending) return <Loading />
  if (keymap.error) return <QueryError error={keymap.error} />
  if (!keymap.data) return null

  return (
    <>
      <div className="keys-head">
        <h1>Carte des touches</h1>
        <a className="btn small" href={api.keybindsExportUrl()} download>
          ⭳ Exporter en JSON
        </a>
      </div>

      <p className="muted keys-intro">
        Mémo de l'assignation Skyrim / Nolvus. Clique une touche pour lui donner une action,
        une famille et un mémo — <strong>où</strong> elle se modifie (MCM, ini, JSON). Rien
        n'est lu ni écrit côté jeu : c'est une carte, pas un outil de remappage.
      </p>

      <div className="keymap-surface">
        <Keyboard
          keymap={keymap.data}
          filterCat={filterCat}
          search={search}
          onSearch={setSearch}
          onFilter={setFilterCat}
          onEdit={setEditing}
        />
      </div>

      {editing !== null && (
        <KeyEditor
          keymap={keymap.data}
          scanCode={editing}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  )
}

function Keyboard({
  keymap,
  filterCat,
  search,
  onSearch,
  onFilter,
  onEdit,
}: {
  keymap: Keymap
  filterCat: string | null
  search: string
  onSearch: (value: string) => void
  onFilter: (cat: string | null) => void
  onEdit: (scanCode: number) => void
}) {
  const binds = useMemo(
    () => new Map(keymap.binds.map((bind) => [bind.scan_code, bind])),
    [keymap.binds],
  )
  const palettes = useMemo(
    () => new Map(keymap.categories.map((cat) => [cat.key, cat])),
    [keymap.categories],
  )

  const needle = search.trim().toLowerCase()

  /** Une touche est « touchée » par les filtres actifs (famille et/ou recherche). */
  function matches(code: number): boolean {
    if (!filterCat && !needle) return true
    const bind = binds.get(code)
    if (!bind) return false
    if (filterCat && bind.cat !== filterCat) return false
    if (needle) {
      const haystack = `${bind.action} ${bind.note ?? ''}`.toLowerCase()
      if (!haystack.includes(needle)) return false
    }
    return true
  }

  const filtering = Boolean(filterCat || needle)

  function cap(key: Key) {
    const bind = binds.get(key.code)
    const palette = bind ? palettes.get(bind.cat) : undefined
    const colors = palette ?? keymap.free_key
    const hit = matches(key.code)

    return (
      <button
        key={key.code}
        type="button"
        className={[
          'keycap',
          bind ? 'bound' : 'free',
          filtering && !hit ? 'dimmed' : '',
          filtering && hit ? 'hit' : '',
        ]
          .filter(Boolean)
          .join(' ')}
        style={
          {
            '--ink': colors.ink,
            '--edge': colors.edge,
            '--face': colors.face,
            '--u': key.width,
          } as React.CSSProperties
        }
        title={
          bind
            ? `${bind.action} — scan code ${key.code}`
            : `Touche libre — scan code ${key.code}`
        }
        onClick={() => onEdit(key.code)}
      >
        <span className="cap-legend">{key.legend}</span>
        {bind && <span className="cap-action">{bind.action}</span>}
      </button>
    )
  }

  return (
    <>
      <div className="keymap-toolbar">
        <label className="grow">
          Chercher une action ou un mémo
          <input
            type="text"
            value={search}
            placeholder="ex. parade, MCM, esquive…"
            onChange={(event) => onSearch(event.target.value)}
          />
        </label>
        {filtering && (
          <button
            type="button"
            className="btn small"
            onClick={() => {
              onFilter(null)
              onSearch('')
            }}
          >
            Effacer les filtres
          </button>
        )}
      </div>

      <div className="keymap-board">
        <div className="board keyboard">
          {keymap.layout.rows.map((row, index) => (
            <div className="key-row" key={index}>
              {row.map(cap)}
            </div>
          ))}
        </div>

        <div className="board numpad">
          <div className="board-title">Pavé</div>
          {keymap.layout.numpad.map((row, index) => (
            <div className="key-row" key={index}>
              {row.map(cap)}
            </div>
          ))}
        </div>

        <div className="board mouse">
          <div className="board-title">Souris</div>
          <div className="key-row mouse-top">{keymap.layout.mouse_buttons.map(cap)}</div>
          {keymap.layout.mouse_side.map((key) => (
            <div className="key-row" key={key.code}>
              {cap(key)}
            </div>
          ))}
        </div>
      </div>

      {/* La légende devient un filtre : cliquer une famille isole ses touches. */}
      <div className="legend">
        {keymap.categories.map((cat) => (
          <span
            key={cat.key}
            className={`legend-item filterable ${filterCat === cat.key ? 'active' : ''}`}
            style={
              { '--ink': cat.ink, '--edge': cat.edge, '--face': cat.face } as React.CSSProperties
            }
            role="button"
            tabIndex={0}
            onClick={() => onFilter(filterCat === cat.key ? null : cat.key)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onFilter(filterCat === cat.key ? null : cat.key)
              }
            }}
          >
            <span className="legend-chip" />
            {cat.label}
            <span className="legend-count">{keymap.counts[cat.key] ?? 0}</span>
          </span>
        ))}
        <span
          className="legend-item legend-free"
          style={
            {
              '--ink': keymap.free_key.ink,
              '--edge': keymap.free_key.edge,
              '--face': keymap.free_key.face,
            } as React.CSSProperties
          }
        >
          <span className="legend-chip" />
          Libre
          <span className="legend-count">{keymap.free_count}</span>
        </span>
      </div>
    </>
  )
}

function KeyEditor({
  keymap,
  scanCode,
  onClose,
}: {
  keymap: Keymap
  scanCode: number
  onClose: () => void
}) {
  const bind: KeyBind | undefined = keymap.binds.find((b) => b.scan_code === scanCode)
  const legend = findLegend(keymap, scanCode)
  const defaultCat = keymap.categories[0]?.key ?? ''

  const [action, setAction] = useState(bind?.action ?? '')
  const [cat, setCat] = useState(bind?.cat ?? defaultCat)
  const [note, setNote] = useState(bind?.note ?? '')

  const save = useSetKeybind()
  const clear = useClearKeybind()
  const panelRef = useRef<HTMLFormElement>(null)
  const actionRef = useRef<HTMLInputElement>(null)

  useEffect(() => actionRef.current?.focus(), [])

  // Échap ferme, clic hors du panneau ferme — comme l'ancien keymap.js, mais sans
  // avoir à deviner si un clic sur un keycap ouvrait un autre panneau.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    function onClick(event: MouseEvent) {
      const target = event.target as HTMLElement
      if (panelRef.current?.contains(target)) return
      if (target.closest('.keycap')) return
      onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('click', onClick)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('click', onClick)
    }
  }, [onClose])

  function submit() {
    // Une action vidée vaut libération : c'est le geste naturel quand on efface
    // le champ, et l'ancienne interface le faisait déjà.
    if (!action.trim()) {
      if (bind) clear.mutate(scanCode, { onSuccess: onClose })
      else onClose()
      return
    }
    save.mutate({ scanCode, action: action.trim(), cat, note }, { onSuccess: onClose })
  }

  const busy = save.isPending || clear.isPending

  return (
    <div className="key-editor">
      <form
        ref={panelRef}
        className="key-editor-panel"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <div className="editor-head">
          <span className="editor-cap">{legend}</span>
          <div>
            <div className="editor-title">Assignation</div>
            <div className="editor-code">
              scan code <code>{scanCode}</code>
            </div>
          </div>
          <button
            type="button"
            className="editor-close btn small"
            title="Fermer (Échap)"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {save.error && <QueryError error={save.error} />}

        <label>
          Action
          <input
            ref={actionRef}
            type="text"
            value={action}
            autoComplete="off"
            placeholder="ex. Attaque puissante"
            onChange={(event) => setAction(event.target.value)}
          />
        </label>

        <div className="pill-block">
          <span className="pill-legend">Famille</span>
          <div className="pills">
            {keymap.categories.map((category: KeyCategory) => (
              <label
                key={category.key}
                className="pill"
                style={
                  {
                    '--ink': category.ink,
                    '--edge': category.edge,
                    '--face': category.face,
                  } as React.CSSProperties
                }
              >
                <input
                  type="radio"
                  name="cat"
                  value={category.key}
                  checked={cat === category.key}
                  onChange={() => setCat(category.key)}
                />
                <span>{category.label}</span>
              </label>
            ))}
          </div>
        </div>

        <label>
          Mémo
          <textarea
            rows={4}
            value={note}
            placeholder="Où se modifie cette touche ? MCM, ini, JSON… contraintes et pièges."
            onChange={(event) => setNote(event.target.value)}
          />
          <small>Entrée valide depuis le champ action ; ici elle passe à la ligne.</small>
        </label>

        <div className="editor-actions">
          <button type="submit" className="btn primary" disabled={busy}>
            Assigner
            {busy && <span className="spinner" />}
          </button>
          {bind && (
            <button
              type="button"
              className="btn danger"
              disabled={busy}
              onClick={() => clear.mutate(scanCode, { onSuccess: onClose })}
            >
              Libérer
            </button>
          )}
        </div>
      </form>
    </div>
  )
}

/** Légende physique d'un scan code, cherchée dans toute la disposition. */
function findLegend(keymap: Keymap, scanCode: number): string {
  const all = [
    ...keymap.layout.rows.flat(),
    ...keymap.layout.numpad.flat(),
    ...keymap.layout.mouse_buttons,
    ...keymap.layout.mouse_side,
  ]
  return all.find((key) => key.code === scanCode)?.legend ?? String(scanCode)
}
