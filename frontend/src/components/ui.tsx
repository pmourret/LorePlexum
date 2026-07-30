import type { ReactNode } from 'react'

import { ApiError, type LogMessage } from '../api/client'

/** Petits composants partagés, calqués sur les classes du thème. */

const ALERT_ICONS = { success: '✅', error: '❌', warning: '⚠️' } as const

/** Doublure textuelle de l'icône : « ❌ » se lit « croix » chez la plupart des
 *  synthèses vocales, ce qui ne dit pas de quoi il s'agit. */
const ALERT_LABELS = {
  success: 'Succès :',
  error: 'Erreur :',
  warning: 'Avertissement :',
} as const

export function Alert({
  level,
  children,
}: {
  level: 'success' | 'error' | 'warning'
  children: ReactNode
}) {
  return (
    // `alert` (assertif) pour une erreur, `status` (poli) sinon : une erreur doit
    // interrompre la lecture en cours, une confirmation peut attendre la fin de la
    // phrase. Sans rôle du tout, une alerte apparue après coup dans une SPA n'était
    // simplement jamais annoncée — la page ne recharge plus.
    <div className={`alert ${level}`} role={level === 'error' ? 'alert' : 'status'}>
      <span className="alert-icon" aria-hidden="true">
        {ALERT_ICONS[level]}
      </span>
      <span className="alert-body">
        <span className="sr-only">{ALERT_LABELS[level]} </span>
        {children}
      </span>
    </div>
  )
}

export function Loading({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="spinner on-dark" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

/**
 * Spinner accolé au libellé d'un bouton pendant une mutation.
 *
 * Toujours `aria-hidden` : le bouton est déjà `disabled` et son libellé ne change
 * pas, l'information « ça travaille » passe par `aria-busy` sur le formulaire, pas
 * par une décoration qui se ferait lire « image ».
 */
export function ButtonSpinner({ dark = false }: { dark?: boolean }) {
  return <span className={dark ? 'spinner on-dark' : 'spinner'} aria-hidden="true" />
}

/**
 * Rendu d'une erreur de requête.
 *
 * Une configuration invalide (`503`) n'est pas une panne : c'est un état normal
 * de l'application tant que les chemins ne sont pas renseignés, et l'alerte du
 * bandeau le dit déjà. On reste discret plutôt que d'empiler deux messages
 * rouges sur la même page.
 */
export function QueryError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.isConfigurationError) {
    return <p className="muted">Indisponible tant que la configuration est incomplète.</p>
  }
  const message = error instanceof Error ? error.message : String(error)
  return <Alert level="error">{message}</Alert>
}

const LOG_ICONS: Record<string, string> = {
  success: '✅',
  error: '❌',
  info: 'ℹ️',
  warning: '⚠️',
}

const LOG_LABELS: Record<string, string> = {
  success: 'Succès',
  error: 'Erreur',
  info: 'Info',
  warning: 'Avertissement',
}

/** Journal d'exécution renvoyé par le pipeline (`Reporter`). */
export function ExecutionLog({ messages }: { messages: LogMessage[] }) {
  if (!messages.length) return null
  return (
    <>
      <h3 className="logs-title">Journal d'exécution</h3>
      <ul className="logs">
        {messages.map((message, index) => (
          <li key={index} className={`log ${message.level}`}>
            <span className="log-icon" aria-hidden="true">
              {LOG_ICONS[message.level] ?? '•'}
            </span>
            <span className="log-msg">
              {/* Le niveau n'est porté que par la couleur et l'émoji ; à l'oreille
                  comme en niveaux de gris, les deux disparaissent. */}
              <span className="sr-only">{LOG_LABELS[message.level] ?? message.level} : </span>
              {message.message}
            </span>
          </li>
        ))}
      </ul>
    </>
  )
}
