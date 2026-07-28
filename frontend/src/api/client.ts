import type { components } from './schema'

/**
 * Enveloppe `fetch` minimale au-dessus du contrat généré.
 *
 * Les types viennent de `schema.d.ts`, produit par `npm run generate:api` depuis
 * les schémas Pydantic du backend : le contrat n'est jamais écrit à la main des
 * deux côtés, et une divergence se voit à la compilation.
 *
 * Les requêtes sont relatives (`/api/v1/...`), donc toujours same-origin : le
 * proxy Vite en développement et Traefik en production servent l'API et cette
 * page sur le même host.
 */

export type Schemas = components['schemas']

export type Category = Schemas['Category']
export type ConfigStatus = Schemas['ConfigStatusOut']
export type CalendarData = Schemas['CalendarOut']
export type GameDate = Schemas['GameDate']
export type SuggestedDate = Schemas['SuggestedDateOut']
export type InjectionCreate = Schemas['InjectionCreate']
export type InjectionResult = Schemas['InjectionResultOut']
export type InjectionSummary = Schemas['InjectionSummary']
export type InjectionDetail = Schemas['InjectionDetail']
export type InjectionPage = Schemas['InjectionPage']
export type InjectionFacets = Schemas['InjectionFacets']
export type LogMessage = Schemas['LogMessage']
export type Keymap = Schemas['KeymapOut']
export type KeyBind = Schemas['KeyBind']
export type KeyCategory = Schemas['KeyCategory']
export type Key = Schemas['Key']
export type Settings = Schemas['SettingsOut']
export type SettingCheck = Schemas['SettingCheck']

const BASE = '/api/v1'

/**
 * Erreur HTTP portant le corps de la réponse.
 *
 * Le backend distingue les cas par le statut, et l'interface s'en sert :
 * `409` = doublon (le corps contient l'injection existante et le journal),
 * `503` = configuration invalide (il faut renvoyer vers les Paramètres),
 * `422` = validation.
 */
export class ApiError<T = unknown> extends Error {
  readonly status: number
  readonly body: T

  constructor(status: number, body: T, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }

  /** Configuration applicative absente ou invalide. */
  get isConfigurationError(): boolean {
    return this.status === 503
  }

  /** Texte déjà injecté : rejouable avec `allow_duplicate`. */
  get isDuplicate(): boolean {
    return this.status === 409
  }
}

/** Extrait un message lisible d'un corps d'erreur FastAPI. */
function readDetail(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    // Erreur de validation Pydantic : liste de {loc, msg, type}.
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : null,
        )
        .filter((msg): msg is string => msg !== null)
      if (messages.length) return messages.join(' ; ')
    }
  }
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })

  if (response.status === 204) return undefined as T

  const text = await response.text()
  const body = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw new ApiError(
      response.status,
      body,
      readDetail(body, `${response.status} ${response.statusText}`),
    )
  }
  return body as T
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const serialized = search.toString()
  return serialized ? `?${serialized}` : ''
}

export const api = {
  health: () => request<ConfigStatus>('/health'),
  categories: () => request<Category[]>('/categories'),
  arcs: () => request<string[]>('/arcs'),
  metadataFiles: () => request<string[]>('/metadata-files'),
  metadataFile: (filename: string) =>
    request<Record<string, unknown>>(`/metadata-files/${encodeURIComponent(filename)}`),

  calendar: () => request<CalendarData>('/calendar'),
  suggestDate: (category: string) =>
    request<SuggestedDate>(`/calendar/suggest${query({ category })}`),

  createInjection: (payload: InjectionCreate) =>
    request<InjectionResult>('/injections', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  injections: (params: {
    categorie?: string
    arc?: string
    search?: string
    page?: number
    per_page?: number
  }) => request<InjectionPage>(`/injections${query(params)}`),
  facets: () => request<InjectionFacets>('/injections/facets'),
  injection: (id: number) => request<InjectionDetail>(`/injections/${id}`),
  pdfUrl: (id: number) => `${BASE}/injections/${id}/pdf`,

  keymap: () => request<Keymap>('/keymap'),
  setKeybind: (scanCode: number, payload: Schemas['KeyBindWrite']) =>
    request<KeyBind>(`/keybinds/${scanCode}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  clearKeybind: (scanCode: number) =>
    request<void>(`/keybinds/${scanCode}`, { method: 'DELETE' }),
  keybindsExportUrl: () => `${BASE}/keybinds/export`,

  settings: () => request<Settings>('/settings'),
  saveSettings: (values: Record<string, string>) =>
    request<Settings>('/settings', {
      method: 'PUT',
      body: JSON.stringify({ values }),
    }),
}
