import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query'

import { api, type InjectionCreate, type Schemas } from './client'

/**
 * Hooks TanStack Query — le cache serveur de l'application.
 *
 * Les clés sont regroupées ici plutôt que dispersées dans les pages : une
 * invalidation après écriture doit pouvoir cibler exactement ce qui a changé, et
 * c'est intenable si les clés sont écrites à la main à cinq endroits.
 */

export const keys = {
  health: ['health'] as const,
  categories: ['categories'] as const,
  arcs: ['arcs'] as const,
  metadataFiles: ['metadata-files'] as const,
  calendar: ['calendar'] as const,
  suggestedDate: (category: string) => ['calendar', 'suggest', category] as const,
  injections: (params: unknown) => ['injections', params] as const,
  facets: ['injections', 'facets'] as const,
  injection: (id: number) => ['injections', id] as const,
  keymap: ['keymap'] as const,
  settings: ['settings'] as const,
}

/** Données statiques : inutile de les refetcher, elles ne changent pas. */
const STATIC = {
  staleTime: Infinity,
  gcTime: Infinity,
} satisfies Partial<UseQueryOptions>

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health })
}

export function useCategories() {
  return useQuery({ queryKey: keys.categories, queryFn: api.categories, ...STATIC })
}

/**
 * Le calendrier tamrielien ne bouge jamais : un seul appel pour toute la session.
 *
 * C'est ce qui remplace les allers-retours `/suggest-date` et `/date-days` de
 * l'ancienne interface — le nombre de jours par mois arrive avec les données, le
 * sélecteur les recalcule localement.
 */
export function useCalendar() {
  return useQuery({ queryKey: keys.calendar, queryFn: api.calendar, ...STATIC })
}

export function useArcs(enabled = true) {
  return useQuery({ queryKey: keys.arcs, queryFn: api.arcs, enabled, retry: false })
}

export function useMetadataFiles(enabled = true) {
  return useQuery({
    queryKey: keys.metadataFiles,
    queryFn: api.metadataFiles,
    enabled,
    retry: false,
  })
}

export function useSuggestedDate(category: string, enabled = true) {
  return useQuery({
    queryKey: keys.suggestedDate(category),
    queryFn: () => api.suggestDate(category),
    enabled: enabled && Boolean(category),
    retry: false,
  })
}

export function useInjections(params: {
  categorie?: string
  arc?: string
  search?: string
  page?: number
  per_page?: number
}) {
  return useQuery({
    queryKey: keys.injections(params),
    queryFn: () => api.injections(params),
    placeholderData: (previous) => previous, // évite le clignotement à la pagination
  })
}

export function useFacets() {
  return useQuery({ queryKey: keys.facets, queryFn: api.facets })
}

export function useInjection(id: number) {
  return useQuery({
    queryKey: keys.injection(id),
    queryFn: () => api.injection(id),
    enabled: Number.isFinite(id),
  })
}

export function useCreateInjection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: InjectionCreate) => api.createInjection(payload),
    onSuccess: () => {
      // Une injection touche l'historique, ses facettes et la liste des arcs.
      queryClient.invalidateQueries({ queryKey: ['injections'] })
      queryClient.invalidateQueries({ queryKey: keys.arcs })
      queryClient.invalidateQueries({ queryKey: ['calendar', 'suggest'] })
    },
  })
}

export function useKeymap() {
  return useQuery({ queryKey: keys.keymap, queryFn: api.keymap })
}

export function useSetKeybind() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      scanCode,
      ...payload
    }: Schemas['KeyBindWrite'] & { scanCode: number }) =>
      api.setKeybind(scanCode, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.keymap }),
  })
}

export function useClearKeybind() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (scanCode: number) => api.clearKeybind(scanCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.keymap }),
  })
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: api.settings })
}

export function useSaveSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values: Record<string, string>) => api.saveSettings(values),
    onSuccess: (data) => {
      queryClient.setQueryData(keys.settings, data)
      // Les chemins ont pu changer : tout ce qui en dépend est désormais suspect.
      queryClient.invalidateQueries({ queryKey: keys.health })
      queryClient.invalidateQueries({ queryKey: keys.arcs })
      queryClient.invalidateQueries({ queryKey: keys.metadataFiles })
    },
  })
}
