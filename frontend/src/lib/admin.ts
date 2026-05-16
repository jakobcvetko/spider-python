import { useCallback, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './api'

export type AdminUser = {
  id: string
  email: string
  display_name: string | null
  is_admin: boolean
  created_at: string
  updated_at: string
}

export type ScraperEvent = {
  id: string
  ts: number
  kind: string
  source: string | null
  message: string | null
  data: Record<string, unknown>
}

export type ScraperStatus = {
  connected: boolean
  last_heartbeat_ts: number | null
  seconds_since_heartbeat: number | null
  sources: string[]
  interval_seconds: number
  recent_events: ScraperEvent[]
}

export type RunSourceResponse = {
  queued: boolean
  reason: string
  source: string
}

export type AdminListing = {
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
  created_at: string
  updated_at: string
}

export const adminKeys = {
  users: ['admin', 'users'] as const,
  scraperStatus: ['admin', 'scraper', 'status'] as const,
  listings: ['admin', 'listings'] as const,
  bolhaProgressive: ['admin', 'bolha', 'progressive'] as const,
  bolhaAdStates: ['admin', 'bolha', 'ad-states'] as const,
  bolhaAds: ['admin', 'bolha', 'ads'] as const,
}

/** Highest ad_id rows shown on the live bolha_ads registry table. */
export const BOLHA_ADS_TOP_LIMIT = 50

export function useAdminUsers(enabled: boolean) {
  return useQuery<AdminUser[]>({
    queryKey: adminKeys.users,
    queryFn: async () => {
      const { data } = await api.get<AdminUser[]>('/admin/users')
      return data
    },
    enabled,
    refetchInterval: 30_000,
  })
}

export type BolhaProgressiveRow = {
  ad_id: number
  zone: string
  display_status: string
  outcome: string | null
  http_status: number | null
  gtm_ad_status: string | null
  fetched_at: string | null
  inactive_age_seconds: number | null
  detail: string | null
  pipeline_status: string | null
}

export type BolhaProgressiveState = {
  look_ahead_count: number
  last_working_ad_id: number
  last_working_at: string | null
  scan_anchor_ad_id: number
  last_homepage_max: number
  last_fetch_high_water: number
  last_fetch_started_at: string | null
  db_numeric_max: number
  lookahead_rows: BolhaProgressiveRow[]
  pivot_row: BolhaProgressiveRow
  tail_rows: BolhaProgressiveRow[]
}

export type BolhaAdStateRow = {
  ad_id: number
  status: string
  last_lookahead_at: string | null
  first_fallback_scrape_at: string | null
  last_fallback_scrape_at: string | null
  last_outcome: string | null
  last_detail: string | null
  created_at: string
  updated_at: string
}

export type BolhaAdScrapeEntry = {
  offset_seconds: number
  at: string
  source: string
  result: string
  http_status: number | null
  detail: string | null
}

export type BolhaAdRow = {
  ad_id: number
  status: string
  created_at: string
  updated_at: string
  scrapes: BolhaAdScrapeEntry[]
}

/** Bolha iAPI probe URL (works for any ad ID without knowing the slug). */
export function bolhaAdUrl(adId: number): string {
  return `https://iapi.bolha.com/avtomobili/progressive-scrape-oglas-${adId}`
}

export function useBolhaAds(enabled: boolean, limit = BOLHA_ADS_TOP_LIMIT) {
  return useQuery<BolhaAdRow[]>({
    queryKey: [...adminKeys.bolhaAds, limit] as const,
    queryFn: async () => {
      const { data } = await api.get<BolhaAdRow[]>('/admin/bolha/ads', {
        params: { limit },
      })
      return data
    },
    enabled,
    refetchInterval: enabled ? 2_000 : false,
  })
}

export function useBolhaAdStates(enabled: boolean, limit = 10_000) {
  return useQuery<BolhaAdStateRow[]>({
    queryKey: [...adminKeys.bolhaAdStates, limit] as const,
    queryFn: async () => {
      const { data } = await api.get<BolhaAdStateRow[]>('/admin/bolha/ad-states', {
        params: { limit },
      })
      return data
    },
    enabled,
    refetchInterval: enabled ? 500 : false,
  })
}

export function useBolhaProgressiveState(enabled: boolean) {
  return useQuery<BolhaProgressiveState>({
    queryKey: adminKeys.bolhaProgressive,
    queryFn: async () => {
      const { data } = await api.get<BolhaProgressiveState>('/admin/bolha/progressive-state')
      return data
    },
    enabled,
    refetchInterval: enabled ? 500 : false,
  })
}

export function useAdminListings(enabled: boolean) {
  return useQuery<AdminListing[]>({
    queryKey: adminKeys.listings,
    queryFn: async () => {
      const { data } = await api.get<AdminListing[]>('/admin/listings', {
        params: { limit: 100 },
      })
      return data
    },
    enabled,
    refetchInterval: 30_000,
  })
}

export function useScraperStatus(enabled: boolean) {
  return useQuery<ScraperStatus>({
    queryKey: adminKeys.scraperStatus,
    queryFn: async () => {
      const { data } = await api.get<ScraperStatus>('/admin/scraper/status')
      return data
    },
    enabled,
  })
}

export function useTriggerScraper() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ queued: boolean; reason: string }>(
        '/admin/scraper/trigger',
      )
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.scraperStatus })
      qc.invalidateQueries({ queryKey: adminKeys.listings })
      qc.invalidateQueries({ queryKey: adminKeys.bolhaProgressive })
      qc.invalidateQueries({ queryKey: adminKeys.bolhaAdStates })
      qc.invalidateQueries({ queryKey: adminKeys.bolhaAds })
    },
  })
}

export function useRunSourceScrape() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (source: string) => {
      const { data } = await api.post<RunSourceResponse>('/admin/scraper/run-source', {
        source,
      })
      return data
    },
    onSuccess: (_data, source) => {
      qc.invalidateQueries({ queryKey: adminKeys.scraperStatus })
      qc.invalidateQueries({ queryKey: adminKeys.listings })
      if (
        source === 'bolha.com' ||
        source === 'bolha.lookahead' ||
        source === 'bolha.backfill' ||
        source === 'bolha.scout'
      ) {
        qc.invalidateQueries({ queryKey: adminKeys.bolhaProgressive })
        qc.invalidateQueries({ queryKey: adminKeys.bolhaAdStates })
        qc.invalidateQueries({ queryKey: adminKeys.bolhaAds })
      }
    },
  })
}

type WsSnapshot = {
  kind: 'snapshot'
  events: ScraperEvent[]
  status: ScraperStatus
}
type WsEvent = { kind: 'event'; event: ScraperEvent }
type WsStatus = { kind: 'status'; status: ScraperStatus }
type WsMessage = WsSnapshot | WsEvent | WsStatus

export type ScraperLive = {
  status: ScraperStatus | null
  events: ScraperEvent[]
  socketConnected: boolean
  clearEvents: () => void
}

const MAX_LIVE_EVENTS = 200

function wsUrlFor(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${path}`
}

export function useScraperLive(enabled: boolean): ScraperLive {
  const [status, setStatus] = useState<ScraperStatus | null>(null)
  const [events, setEvents] = useState<ScraperEvent[]>([])
  const [socketConnected, setSocketConnected] = useState(false)

  useEffect(() => {
    if (!enabled) return

    // All state for this connection lifecycle is closure-scoped so that
    // stale handlers from a previous effect run (React 19 StrictMode mounts
    // every effect twice in dev) can't touch the current socket or trigger
    // a reconnect cascade. The old bug: an old socket's onclose would fire
    // after the new mount, null out the shared ref, and schedule another
    // connect — leaving multiple live sockets all delivering the same
    // events to setEvents, multiplying every incoming heartbeat.
    let alive = true
    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (!alive) return
      const ws = new WebSocket(wsUrlFor('/api/admin/scraper/ws'))
      socket = ws

      ws.onopen = () => {
        if (!alive || ws !== socket) return
        setSocketConnected(true)
      }
      ws.onclose = () => {
        if (!alive || ws !== socket) return
        setSocketConnected(false)
        socket = null
        reconnectTimer = setTimeout(connect, 1500)
      }
      ws.onerror = () => {
        // onclose will follow and handle reconnect.
      }
      ws.onmessage = (e) => {
        if (!alive || ws !== socket) return
        try {
          const msg = JSON.parse(e.data) as WsMessage
          if (msg.kind === 'snapshot') {
            setStatus(msg.status)
            setEvents(msg.events.slice(-MAX_LIVE_EVENTS))
          } else if (msg.kind === 'event') {
            const incoming = msg.event
            setEvents((prev) => {
              // Defensive de-dupe: server NOTIFY occasionally fans out the
              // same event through multiple paths during reconnects.
              if (prev.some((existing) => existing.id === incoming.id)) {
                return prev
              }
              const next = prev.concat(incoming)
              return next.length > MAX_LIVE_EVENTS
                ? next.slice(next.length - MAX_LIVE_EVENTS)
                : next
            })
          } else if (msg.kind === 'status') {
            setStatus(msg.status)
          }
        } catch {
          // ignore malformed messages
        }
      }
    }

    connect()

    return () => {
      alive = false
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      const ws = socket
      socket = null
      if (ws && ws.readyState <= WebSocket.OPEN) {
        ws.close()
      }
      setSocketConnected(false)
    }
  }, [enabled])

  const clearEvents = useCallback(() => setEvents([]), [])

  return { status, events, socketConnected, clearEvents }
}
