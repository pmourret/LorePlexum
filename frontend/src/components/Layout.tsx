import { NavLink, Outlet } from 'react-router-dom'

import { useHealth } from '../api/hooks'

const NAV = [
  { to: '/inject', label: 'Injecter' },
  { to: '/history', label: 'Historique' },
  { to: '/keys', label: 'Touches' },
  { to: '/settings', label: 'Paramètres' },
]

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
  const unconfigured = health.data && !health.data.config_ok

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="sigil">📜</span>
          <div>
            <div className="brand-title">Journal d'Abyssiaelle</div>
            <div className="brand-sub">LorePlexum</div>
          </div>
        </div>
        <nav className="nav">
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
          <div className="alert error">
            <span>⚠️</span>
            <span>
              Configuration incomplète ou invalide.
              {health.data?.problems.length ? ` ${health.data.problems.join(' ; ')}.` : ''}
            </span>
            <NavLink className="btn small" to="/settings">
              Ouvrir les paramètres
            </NavLink>
          </div>
        </div>
      )}

      <main className="content">
        <Outlet />
      </main>

      <footer className="foot">Projet Abyssiaelle — outil local d'injection narrative</footer>
    </>
  )
}
