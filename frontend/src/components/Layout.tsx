import { useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { useHealth } from '../api/hooks'

const NAV = [
  { to: '/inject', label: 'Injecter' },
  { to: '/history', label: 'Historique' },
  { to: '/keys', label: 'Touches' },
  { to: '/settings', label: 'Paramètres' },
]

/**
 * Routes qui lèvent la largeur maximale de 1100 px.
 *
 * La carte des touches fait à elle seule ~1100 px : contrainte, elle défilait
 * horizontalement. La liste est ici plutôt que dans la page parce que c'est le
 * `<main>` du Layout qui porte la contrainte — une page ne peut pas la relâcher
 * depuis l'intérieur sans bricolage `100vw`, qui compte la barre de défilement.
 */
const WIDE_ROUTES = ['/keys']

/**
 * Châssis commun : bandeau, navigation, pied de page.
 *
 * Il porte aussi l'alerte de configuration. Dans l'ancienne interface, chaque
 * page revalidait la config à son rendu côté serveur ; ici la SPA ne recharge
 * plus, donc le signal doit être persistant et affiché une seule fois, au-dessus
 * de toutes les pages.
 */
export default function Layout() {
  const health = useHealth()
  const { pathname } = useLocation()
  const unconfigured = health.data && !health.data.config_ok
  const wide = WIDE_ROUTES.some((route) => pathname.startsWith(route))
  const main = useRef<HTMLElement>(null)
  const firstRender = useRef(true)

  /**
   * Changement de page : ramener le défilement en haut et le focus sur `<main>`.
   *
   * Un vrai chargement de page faisait les deux gratuitement. Le routeur, lui, ne
   * touche ni au défilement ni au focus : on arrivait sur « Paramètres » au milieu
   * de la page, et au clavier on repartait du lien de navigation cliqué — donc en
   * ré-parcourant tout l'en-tête pour atteindre le contenu.
   *
   * Pas au premier rendu, en revanche. Focaliser `<main>` dès l'arrivée place le
   * curseur *après* le lien d'évitement : la première tabulation sautait droit
   * dans le formulaire et le lien devenait inatteignable — exactement ce qu'il
   * sert à éviter. Au chargement, le focus doit rester au début du document, comme
   * dans n'importe quelle page.
   *
   * `preventScroll` parce que le focus provoquerait sinon son propre saut, qui
   * annulerait le `scrollTo` juste au-dessus.
   */
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    window.scrollTo(0, 0)
    main.current?.focus({ preventScroll: true })
  }, [pathname])

  return (
    <>
      {/* `href` reste pour la sémantique (c'est un lien, il annonce sa cible), mais
          le focus est déplacé à la main : laisser le navigateur suivre l'ancre
          collerait « #contenu » à l'URL, que le routeur relirait ensuite comme une
          localisation à part entière. */}
      <a
        className="skip-link"
        href="#contenu"
        onClick={(event) => {
          event.preventDefault()
          main.current?.focus()
        }}
      >
        Aller au contenu
      </a>

      <header className="topbar">
        <div className="brand">
          <span className="sigil" aria-hidden="true">
            📜
          </span>
          <div>
            <div className="brand-title">Journal d'Abyssiaelle</div>
            <div className="brand-sub">LorePlexum</div>
          </div>
        </div>
        {/* Une seule navigation dans la page, mais nommée quand même : c'est ce
            libellé qu'annonce la liste des repères d'un lecteur d'écran. */}
        <nav className="nav" aria-label="Navigation principale">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? 'on' : undefined)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {unconfigured && (
        <div className="config-banner">
          <div className="alert error" role="alert">
            <span className="alert-icon" aria-hidden="true">
              ⚠️
            </span>
            <span className="alert-body">
              Configuration incomplète ou invalide.
              {health.data?.problems.length ? ` ${health.data.problems.join(' ; ')}.` : ''}
            </span>
            <NavLink className="btn small" to="/settings">
              Ouvrir les paramètres
            </NavLink>
          </div>
        </div>
      )}

      {/* `tabIndex={-1}` : cible focalisable par programme (lien d'évitement et
          changement de route) sans entrer dans l'ordre de tabulation. */}
      <main
        id="contenu"
        ref={main}
        tabIndex={-1}
        className={wide ? 'content content-wide' : 'content'}
      >
        <Outlet />
      </main>

      <footer className="foot">Projet Abyssiaelle — outil local d'injection narrative</footer>
    </>
  )
}
