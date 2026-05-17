import { useCallback, useEffect, useRef, useState } from 'react'

import { Card, TableFrame } from '../components/ui'
import {
  type ScraperEvent,
  useAvtonetHttpLogs,
  useScraperLive,
} from '../lib/admin'

const LOG_VIEWPORT_HEIGHT = 'min(70vh, 720px)'
const STICK_TO_BOTTOM_THRESHOLD_PX = 48

function fmtTs(ts: number): string {
  const d = new Date(ts * 1000)
  return (
    d.toLocaleTimeString([], { hour12: false }) +
    '.' +
    d.getMilliseconds().toString().padStart(3, '0')
  )
}

function shortUrl(url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname + u.search
    if (path.length > 72) return path.slice(0, 69) + '…'
    return path || u.hostname
  } catch {
    return url.length > 72 ? url.slice(0, 69) + '…' : url
  }
}

function statusTone(status: number | null): string {
  if (status == null) return 'text-zinc-400'
  if (status >= 500) return 'text-red-700'
  if (status >= 400) return 'text-amber-700'
  if (status >= 300) return 'text-sky-700'
  return 'text-emerald-700'
}

function rowStatus(ev: ScraperEvent): number | null {
  if (ev.kind === 'http_response') {
    const st = ev.data?.status
    return typeof st === 'number' ? st : null
  }
  return null
}

function rowElapsed(ev: ScraperEvent): string {
  if (ev.kind !== 'http_response') return '—'
  const ms = ev.data?.elapsed_ms
  return typeof ms === 'number' ? `${ms} ms` : '—'
}

function rowBytes(ev: ScraperEvent): string {
  if (ev.kind !== 'http_response') return '—'
  const bytes = ev.data?.bytes
  if (typeof bytes !== 'number' || bytes <= 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

export default function AdminAvtonetHttpLogsPage() {
  const live = useScraperLive(true)
  const rows = useAvtonetHttpLogs(live.events)
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottomRef = useRef(true)
  const [paused, setPaused] = useState(false)

  const scraperConnected = Boolean(live.status?.connected)

  const isNearBottom = useCallback(() => {
    const el = scrollRef.current
    if (!el) return true
    return (
      el.scrollHeight - el.scrollTop - el.clientHeight <= STICK_TO_BOTTOM_THRESHOLD_PX
    )
  }, [])

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior })
  }, [])

  const onScroll = useCallback(() => {
    const near = isNearBottom()
    stickToBottomRef.current = near
    setPaused(!near)
  }, [isNearBottom])

  useEffect(() => {
    if (!stickToBottomRef.current) return
    scrollToBottom('auto')
  }, [rows, scrollToBottom])

  const onClear = () => {
    stickToBottomRef.current = true
    setPaused(false)
    live.clearEvents()
  }

  const onJumpToLatest = () => {
    stickToBottomRef.current = true
    setPaused(false)
    scrollToBottom('smooth')
  }

  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Avto.net HTTP logs</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Console-style stream (last 100). New lines append at the bottom; scroll up to
          pause auto-follow.
        </p>
      </header>

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                live.socketConnected
                  ? 'bg-emerald-500'
                  : scraperConnected
                    ? 'bg-amber-500'
                    : 'bg-zinc-400'
              }`}
              aria-hidden
            />
            <span className="text-zinc-600">
              {live.socketConnected
                ? 'Live'
                : scraperConnected
                  ? 'Reconnecting…'
                  : 'Worker offline'}
            </span>
            <span className="text-zinc-300">·</span>
            <span className="text-zinc-500">{rows.length} / 100</span>
            {paused && (
              <>
                <span className="text-zinc-300">·</span>
                <span className="text-amber-700">Paused (scroll)</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            {paused && (
              <button
                type="button"
                onClick={onJumpToLatest}
                className="rounded-md border border-zinc-300 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-zinc-700 hover:bg-zinc-100"
              >
                Jump to latest
              </button>
            )}
            <button
              type="button"
              onClick={onClear}
              disabled={rows.length === 0}
              className="rounded-md border border-zinc-300 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Clear
            </button>
          </div>
        </div>

        <TableFrame
          ref={scrollRef}
          onScroll={onScroll}
          className="overflow-y-auto"
          style={{ height: LOG_VIEWPORT_HEIGHT }}
        >
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="sticky top-0 z-10 bg-zinc-100 text-xs uppercase tracking-wide text-zinc-400 shadow-[0_1px_0_0_rgb(228_228_231)]">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Time</th>
                <th className="px-3 py-2 text-left font-medium">Kind</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-left font-medium">Method</th>
                <th className="px-3 py-2 text-left font-medium">URL</th>
                <th className="px-3 py-2 text-left font-medium">Elapsed</th>
                <th className="px-3 py-2 text-left font-medium">Size</th>
                <th className="px-3 py-2 text-left font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 font-mono text-xs">
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-zinc-500">
                    {scraperConnected
                      ? 'Waiting for avto.net HTTP traffic…'
                      : 'Start the avto.net lookahead worker to see requests here.'}
                  </td>
                </tr>
              ) : (
                rows.map((ev) => {
                  const status = rowStatus(ev)
                  const method =
                    typeof ev.data?.method === 'string' ? ev.data.method : '—'
                  const url =
                    typeof ev.data?.url === 'string' ? ev.data.url : (ev.message ?? '—')
                  return (
                    <tr key={ev.id} className="hover:bg-zinc-50">
                      <td className="whitespace-nowrap px-3 py-1.5 text-zinc-500">
                        {fmtTs(ev.ts)}
                      </td>
                      <td
                        className={`whitespace-nowrap px-3 py-1.5 ${
                          ev.kind === 'http_request' ? 'text-sky-700' : 'text-emerald-700'
                        }`}
                      >
                        {ev.kind === 'http_request' ? 'request' : 'response'}
                      </td>
                      <td
                        className={`whitespace-nowrap px-3 py-1.5 font-semibold ${statusTone(status)}`}
                      >
                        {status ?? '—'}
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5 text-zinc-800">
                        {method}
                      </td>
                      <td
                        className="max-w-md truncate px-3 py-1.5 text-zinc-700"
                        title={url}
                      >
                        {shortUrl(url)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5 text-zinc-600">
                        {rowElapsed(ev)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5 text-zinc-600">
                        {rowBytes(ev)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5 text-zinc-400">
                        {ev.source ?? '—'}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </TableFrame>
      </Card>
    </>
  )
}
