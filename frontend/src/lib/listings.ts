import { useQuery } from '@tanstack/react-query'

import { api } from './api'

export type Listing = {
  id: string
  source: string
  external_id: string
  url: string
  title: string
  price_cents: number | null
  currency: string | null
  location: string | null
  image_url: string | null
  year: number | null
  mileage_km: number | null
  published_at: string | null
  created_at: string
}

export function useListings(enabled: boolean, limit = 200) {
  return useQuery<Listing[]>({
    queryKey: ['listings', limit],
    queryFn: async () => {
      const { data } = await api.get<Listing[]>('/listings', { params: { limit } })
      return data
    },
    enabled,
    refetchInterval: 30_000,
  })
}

export function formatPrice(listing: Pick<Listing, 'price_cents' | 'currency'>): string {
  if (listing.price_cents == null) return '—'
  const value = listing.price_cents / 100
  const currency = listing.currency || 'EUR'
  try {
    return new Intl.NumberFormat('sl-SI', { style: 'currency', currency }).format(value)
  } catch {
    return `${value.toFixed(0)} ${currency}`
  }
}
