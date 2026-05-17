import { useMemo } from 'react'

import { Button, Card } from '../components/ui'
import {
  type ScraperEvent,
  useScraperLive,
  useTriggerScraper,
} from '../lib/admin'
import { getErrorMessage } from '../lib/auth'

const KIND_COLORS: Record<string, string> = {
  http_request: 'text-sky-700',
  http_response: 'text-emerald-700',
  fetch_start: 'text-indigo-600',
  fetch_error: 'text-red-700',
  parsed: 'text-zinc-700',
  parsed_empty: 'text-amber-700',
  parsed_preview: 'text-cyan-700',
  upsert: 'text-emerald-700',
  upsert_error: 'text-red-700',
  cycle_start: 'text-violet-700',
  cycle_done: 'text-violet-700',
  heartbeat: 'text-zinc-500',
  worker_started: 'text-emerald-700',
  worker_stopped: 'text-amber-700',
  trigger_skipped: 'text-amber-700',
  debug_source_start: 'text-violet-700',
  debug_source_done: 'text-violet-700',
  debug_source_unknown: 'text-red-600',
}

function fmtTs(ts: number): string {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString([], { hour12: false }) + '.' +
    d.getMilliseconds().toString().padStart(3, '0')
}

function fmtAge(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function eventLabel(ev: ScraperEvent): string {
  if (ev.message) return ev.message
  if (ev.data && Object.keys(ev.data).length > 0) {
    return JSON.stringify(ev.data)
  }
  return ev.kind
}

export default function AdminPage() {
  const live = useScraperLive(true)
  const trigger = useTriggerScraper()

  const triggerError = trigger.error ? getErrorMessage(trigger.error) : null
  const events = useMemo(() => live.events.slice().reverse(), [live.events])

  const status = live.status
  const scraperConnected = Boolean(status?.connected)

  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Home</h1>
        <p className="mt-1 text-sm text-zinc-400">Scraper status and live events.</p>
      </header>

      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Scraper status
          </h2>

          <div className="mb-4 flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                scraperConnected ? 'bg-emerald-500 shadow-[0_0_8px] shadow-emerald-500/40' : 'bg-zinc-400'
              }`}
              aria-hidden
            />
            <span className="text-sm">
              Worker:{' '}
              <span className={scraperConnected ? 'text-emerald-700' : 'text-zinc-400'}>
                {scraperConnected ? 'connected' : 'offline'}
              </span>
            </span>
          </div>

          <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-xs text-zinc-400">
            <dt>Live socket</dt>
            <dd className={live.socketConnected ? 'text-emerald-700' : 'text-amber-700'}>
              {live.socketConnected ? 'connected' : 'reconnecting…'}
            </dd>
            <dt>Last heartbeat</dt>
            <dd className="text-zinc-800">{fmtAge(status?.seconds_since_heartbeat ?? null)} ago</dd>
            <dt>Interval</dt>
            <dd className="text-zinc-800">{status?.interval_seconds ?? '—'}s</dd>
            <dt>Sources</dt>
            <dd className="text-zinc-800">
              {status?.sources?.length ? status.sources.join(', ') : '—'}
            </dd>
          </dl>

          <div className="mt-4 space-y-2">
            <Button
              onClick={() => trigger.mutate()}
              loading={trigger.isPending}
              disabled={!scraperConnected}
              className="w-full"
            >
              {scraperConnected ? 'Trigger scrape now' : 'Worker offline'}
            </Button>
            {triggerError && (
              <p className="text-xs text-red-600">{triggerError}</p>
            )}
            {trigger.isSuccess && !trigger.isPending && (
              <p className="text-xs text-zinc-500">Trigger sent.</p>
            )}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
              Live event stream
            </h2>
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-500">{events.length} events</span>
              <button
                type="button"
                onClick={live.clearEvents}
                disabled={events.length === 0}
                className="rounded-md border border-zinc-300 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
              >
                Clear
              </button>
            </div>
          </div>
          <div className="max-h-[420px] overflow-y-auto border-y border-zinc-200 bg-zinc-100/80 font-mono text-xs -mx-3 sm:mx-0">
            {events.length === 0 ? (
              <p className="p-4 text-zinc-500">
                Waiting for scraper events…
              </p>
            ) : (
              <ul className="divide-y divide-zinc-100">
                {events.map((ev) => (
                  <li key={ev.id} className="flex gap-3 px-3 py-1.5">
                    <span className="shrink-0 text-zinc-500">{fmtTs(ev.ts)}</span>
                    <span
                      className={`shrink-0 w-32 truncate ${KIND_COLORS[ev.kind] || 'text-zinc-700'}`}
                    >
                      {ev.kind}
                    </span>
                    <span className="shrink-0 w-20 truncate text-zinc-400">
                      {ev.source || '—'}
                    </span>
                    <span className="truncate text-zinc-800">{eventLabel(ev)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </section>
    </>
  )
}
