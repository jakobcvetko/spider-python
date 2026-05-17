import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './api'

export type Scraper = {
  id: string
  name: string
  bolha_enabled: boolean
  avtonet_enabled: boolean
  created_at: string
  updated_at: string
}

export type ScraperPayload = {
  name: string
  bolha_enabled: boolean
  avtonet_enabled: boolean
}

export const scraperKeys = {
  all: ['scrapers'] as const,
}

export function isActiveScraper(scraper: Scraper): boolean {
  return scraper.bolha_enabled || scraper.avtonet_enabled
}

export function countActiveScrapers(scrapers: Scraper[] | undefined): number {
  return (scrapers ?? []).filter(isActiveScraper).length
}

export function useScrapers(enabled = true) {
  return useQuery<Scraper[]>({
    queryKey: scraperKeys.all,
    queryFn: async () => {
      const { data } = await api.get<Scraper[]>('/scrapers')
      return data
    },
    enabled,
  })
}

export function useCreateScraper() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ScraperPayload) => {
      const { data } = await api.post<Scraper>('/scrapers', payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: scraperKeys.all })
    },
  })
}

export function useUpdateScraper() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      ...payload
    }: ScraperPayload & { id: string }) => {
      const { data } = await api.patch<Scraper>(`/scrapers/${id}`, payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: scraperKeys.all })
    },
  })
}

export function useDeleteScraper() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/scrapers/${id}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: scraperKeys.all })
    },
  })
}
