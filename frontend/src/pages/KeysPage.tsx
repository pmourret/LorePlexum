import { useEffect, useMemo, useRef, useState } from 'react'

import { api, type Key, type KeyBind, type KeyCategory, type Keymap } from '../api/client'
import { useClearKeybind, useKeymap, useSetKeybind } from '../api/hooks'
import { ButtonSpinner, Loading, QueryError } from '../components/ui'

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

  /**
   * Touche depuis laquelle le panneau a été ouvert, pour y rendre le focus.
   *
   * Sans ça, fermer le panneau laissait le focus sur un bouton qui vient de
   * disparaître : le navigateur le renvoie alors sur `<body>` et la tabulation
   * suivante repartait du tout début de la page — après cent keycaps.
   */
  const opener = useRef<HTMLElement | null>(null)

  function openEditor(scanCode: number, from: HTMLElement) {
    opener.current = from
    setEditing(scanCode)
  }

  function closeEditor() {
    setEditing(null)
    opener.current?.focus()
    opener.current = null
  }

  if (keymap.isPending) return <Loading label="Chargement de la carte des touches…" />
  if (keymap.error) return <QueryError error={keymap.error} />
  if (!keymap.data) return null

  return (
    <>
      <div className="keys-head">
        <h1>Carte des touches</h1>
        <a className="btn small" href={api.keybindsExportUrl()} download>
          <span aria-hidden="true">⭳</span> Exporter en JSON
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
          onEdit={openEditor}
        />
      </div>

      {editing !== null && (
        // `key` : sans lui, React réutilise l'instance quand on clique une autre
        // touche sans fermer le panneau. Or l'état du formulaire est initialisé au
        // montage — l'en-tête affichait le nouveau scan code et les champs
        // gardaient l'action de la touche précédente, prête à être enregistrée au
        // mauvais endroit.
        <KeyEditor
          key={editing}
          keymap={keymap.data}
          scanCode={editing}
          onClose={closeEditor}
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
  onEdit: (scanCode: number, from: HTMLElement) => void
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

  /** Nombre de touches assignées qui passent les filtres — sert d'état vide. */
  const hitCount = useMemo(
    () => (filtering ? keymap.binds.filter((bind) => matches(bind.scan_code)).length : 0),
    // `matches` est recalculée à chaque rendu ; ses entrées réelles sont celles-ci.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [keymap.binds, filterCat, needle, filtering],
  )

  const activeCat = filterCat ? palettes.get(filterCat) : undefined

  function cap(key: Key) {
    const bind = binds.get(key.code)
    const palette = bind ? palettes.get(bind.cat) : undefined
    const colors = palette ?? keymap.free_key
    const hit = matches(key.code)

    // Le libellé physique est souvent un symbole (« ⇧ », « ↵ ») ou une abréviation :
    // lu seul il ne veut rien dire. `aria-label` porte donc la phrase complète, et
    // le contenu visible est masqué pour ne pas être annoncé deux fois.
    const label = bind
      ? `${key.legend} — ${bind.action} (${palette?.label ?? bind.cat}), scan code ${key.code}`
      : `${key.legend} — touche libre, scan code ${key.code}`

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
            '--h': key.height,
          } as React.CSSProperties
        }
        title={
          bind
            ? `${bind.action} — scan code ${key.code}`
            : `Touche libre — scan code ${key.code}`
        }
        aria-label={label}
        onClick={(event) => onEdit(key.code, event.currentTarget)}
      >
        <span className="cap-legend" aria-hidden="true">
          {key.legend}
        </span>
        {bind && (
          <span className="cap-action" aria-hidden="true">
            {bind.action}
          </span>
        )}
      </button>
    )
  }

  return (
    <>
      <div className="keymap-toolbar">
        <label className="grow">
          Chercher une action ou un mémo
          <input
            type="search"
            value={search}
            placeholder="ex. parade, MCM, esquive…"
            onChange={(event) => onSearch(event.target.value)}
          />
        </label>
        {/* Le bouton est toujours rendu, seulement désactivé : le faire
            apparaître et disparaître décalait le champ de recherche à la
            première frappe, sous le curseur de l'utilisateur. */}
        <button
          type="button"
          className="btn small"
          disabled={!filtering}
          onClick={() => {
            onFilter(null)
            onSearch('')
          }}
        >
          Effacer les filtres
        </button>
      </div>

      {/* Résultat du filtrage annoncé à voix haute : visuellement l'information
          est portée par l'estompage de cent touches, ce qui ne s'entend pas. */}
      <p className="sr-only" role="status">
        {filtering
          ? `${hitCount} touche(s) correspondent aux filtres.`
          : `${keymap.binds.length} touches assignées.`}
      </p>

      {filtering && hitCount === 0 && (
        <p className="keymap-empty muted">
          <span aria-hidden="true">🔍</span>
          <span>
            Aucune touche assignée ne correspond{' '}
            {[
              activeCat ? `à la famille « ${activeCat.label} »` : null,
              needle ? `à « ${search.trim()} »` : null,
            ]
              .filter(Boolean)
              .join(' ni ')}
            .
          </span>
          <button
            type="button"
            className="btn small"
            onClick={() => {
              onFilter(null)
              onSearch('')
            }}
          >
            Tout afficher
          </button>
        </p>
      )}

      <small className="board-hint muted">
        La carte est plus large que l'écran : elle défile latéralement.
      </small>

      {/* `tabIndex` + `role="region"` : sous 900 px le clavier défile de côté, et
          cette zone de défilement est inatteignable au clavier sans être
          focalisable. Même traitement que le tableau de l'historique. */}
      <div
        className="keymap-board"
        tabIndex={0}
        role="region"
        aria-label="Disposition du clavier, du pavé numérique et de la souris"
      >
        {/* Enveloppe de niveau inline : c'est elle qui permet de centrer les trois
            blocs dans le conteneur de défilement. Centrer directement avec
            `justify-content` rendrait le début du clavier inatteignable dès qu'il
            déborde — piège connu des conteneurs flex qui défilent. */}
        <div className="keymap-boards">
          <div className="board keyboard">
            {keymap.layout.rows.map((row, index) => (
              <div className="key-row" key={index}>
                {row.map(cap)}
              </div>
            ))}
          </div>

          {/* Entre le clavier et le pavé, comme sur un clavier physique. Rangées
              flex et non grille : la rangée de la flèche haute n'a qu'une touche,
              que le CSS centre — elle tombe ainsi dans la colonne du milieu sans
              qu'aucune position n'ait à être écrite. */}
          <div className="board navcluster">
            <div className="board-title">Navigation</div>
            {keymap.layout.navigation.map((row, index) => (
              <div className="key-row" key={index}>
                {row.map(cap)}
              </div>
            ))}
          </div>

          <div className="board numpad">
            <div className="board-title">Pavé</div>
            {/* Grille, et non des rangées flex comme le clavier : « + » et
                l'Entrée du pavé font deux rangées de haut. Les touches sont donc
                aplaties en une seule liste et le placement automatique de CSS Grid
                recale de lui-même les rangées qui n'ont que trois touches. */}
            <div className="numpad-grid">{keymap.layout.numpad.flat().map(cap)}</div>
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
      </div>

      {/* La légende devient un filtre : cliquer une famille isole ses touches.
          En <button> et non en <span role="button"> : le rôle bricolé obligeait à
          réimplémenter Entrée et Espace à la main, n'héritait ni de `disabled` ni
          du focus natif, et se perdait dans un formulaire. */}
      <div className="legend" aria-label="Familles d'assignation (filtre)" role="group">
        {keymap.categories.map((cat) => (
          <button
            key={cat.key}
            type="button"
            className={`legend-item filterable ${filterCat === cat.key ? 'active' : ''}`}
            style={
              { '--ink': cat.ink, '--edge': cat.edge, '--face': cat.face } as React.CSSProperties
            }
            // Un filtre est un interrupteur, pas une action ponctuelle : `aria-pressed`
            // est ce qui fait annoncer « activé » / « désactivé » à chaque bascule.
            aria-pressed={filterCat === cat.key}
            onClick={() => onFilter(filterCat === cat.key ? null : cat.key)}
          >
            <span className="legend-chip" aria-hidden="true" />
            {cat.label}
            <span className="legend-count">
              <span className="sr-only">— </span>
              {keymap.counts[cat.key] ?? 0}
              <span className="sr-only"> touches</span>
            </span>
          </button>
        ))}
        {/* « Libre » n'est pas un filtre : aucune assignation à isoler. Il reste
            un simple repère de légende. */}
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
          <span className="legend-chip" aria-hidden="true" />
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
    // `role="dialog"` sans `aria-modal` : le panneau flotte au-dessus de la carte
    // mais ne la bloque pas — cliquer une autre touche est un geste voulu. Le
    // déclarer modal mentirait sur ce qui reste atteignable.
    <div
      className="key-editor"
      role="dialog"
      aria-labelledby="key-editor-title"
      aria-busy={busy}
    >
      <form
        ref={panelRef}
        className="key-editor-panel"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <div className="editor-head">
          <span className="editor-cap" aria-hidden="true">
            {legend}
          </span>
          <div>
            <div className="editor-title" id="key-editor-title">
              Assignation — {legend}
            </div>
            <div className="editor-code">
              scan code <code>{scanCode}</code>
            </div>
          </div>
          <button
            type="button"
            className="editor-close btn small"
            aria-label="Fermer le panneau d'assignation (Échap)"
            title="Fermer (Échap)"
            onClick={onClose}
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>

        {/* Les deux mutations, pas seulement l'enregistrement : un échec de
            « Libérer » ne remontait nulle part, le panneau restait simplement
            ouvert sans explication. */}
        {save.error && <QueryError error={save.error} />}
        {clear.error && <QueryError error={clear.error} />}

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
          <small>
            {bind
              ? 'Vider ce champ puis valider libère la touche.'
              : 'Laisser vide et valider ferme le panneau sans rien assigner.'}
          </small>
        </label>

        {/* `<fieldset>`/`<legend>` et non `<div>`/`<span>` : c'est ce qui fait
            annoncer « Famille, bouton radio 3 sur 8 » au lieu du seul libellé de la
            pastille, sorti de tout contexte. */}
        <fieldset className="pill-block">
          <legend className="pill-legend">Famille</legend>
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
        </fieldset>

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
            {save.isPending ? 'Enregistrement…' : 'Assigner'}
            {save.isPending && <ButtonSpinner />}
          </button>
          {bind && (
            <button
              type="button"
              className="btn danger"
              disabled={busy}
              onClick={() => clear.mutate(scanCode, { onSuccess: onClose })}
            >
              {clear.isPending ? 'Libération…' : 'Libérer'}
              {clear.isPending && <ButtonSpinner dark />}
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
