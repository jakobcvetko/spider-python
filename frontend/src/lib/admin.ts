import { useEffect, useRef, useState } from 'react'
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

export const adminKeys = {
  users: ['admin', 'users'] as const,
  scraperStatus: ['admin', 'scraper', 'status'] as const,
}

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
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const stoppedRef = useRef(false)

  useEffect(() => {
    if (!enabled) return

    stoppedRef.current = false

    const connect = () => {
      const ws = new WebSocket(wsUrlFor('/api/admin/scraper/ws'))
      wsRef.current = ws

      ws.onopen = () => setSocketConnected(true)
      ws.onclose = () => {
        setSocketConnected(false)
        wsRef.current = null
        if (!stoppedRef.current) {
          reconnectRef.current = setTimeout(connect, 1500)
        }
      }
      ws.onerror = () => {
        // onclose will follow and trigger reconnect
      }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data) as WsMessage
          if (msg.kind === 'snapshot') {
            setStatus(msg.status)
            setEvents(msg.events.slice(-MAX_LIVE_EVENTS))
          } else if (msg.kind === 'event') {
            setEvents((prev) => {
              const next = prev.concat(msg.event)
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
      stoppedRef.current = true
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
      const ws = wsRef.current
      wsRef.current = null
      if (ws && ws.readyState <= WebSocket.OPEN) {
        ws.close()
      }
      setSocketConnected(false)
    }
  }, [enabled])

  return { status, events, socketConnected }
}
