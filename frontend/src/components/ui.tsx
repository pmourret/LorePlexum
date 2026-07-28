import type { ReactNode } from 'react'

import { ApiError, type LogMessage } from '../api/client'

/** Petits composants partagés, calqués sur les classes du thème. */

export function Alert({
  level,
  children,
}: {
  level: 'success' | 'error' | 'warning'
  children: ReactNode
}) {
  const icon = { success: '✅', error: '❌', warning: '⚠️' }[level]
  return (
    <div className={`alert ${level}`}>
      <span>{icon}</span>
      <span>{children}</span>
    </div>
  )
}

export function Loading({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="loading">
      <span className="spinner on-dark" />
      <span>{label}</span>
    </div>
  )
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

/** Journal d'exécution renvoyé par le pipeline (`Reporter`). */
export function ExecutionLog({ messages }: { messages: LogMessage[] }) {
  if (!messages.length) return null
  return (
    <>
      <h3 className="logs-title">Journal d'exécution</h3>
      <ul className="logs">
        {messages.map((message, index) => (
          <li key={index} className={`log ${message.level}`}>
            <span className="log-icon">{LOG_ICONS[message.level] ?? '•'}</span>
            <span className="log-msg">{message.message}</span>
          </li>
        ))}
      </ul>
    </>
  )
}
