import { useMemo, type ReactNode } from 'react'
import { Button, Card } from './ui'
import {
  type ScraperEvent,
  type ScraperLive,
  useRunSourceScrape,
  useScraperLive,
} from '../lib/admin'
import { getErrorMessage } from '../lib/auth'

const KIND_COLORS: Record<string, string> = {
  http_request: 'text-sky-300',
  http_response: 'text-emerald-300',
  fetch_start: 'text-indigo-300',
  fetch_error: 'text-red-300',
  parsed: 'text-zinc-300',
  parsed_empty: 'text-amber-300',
  parsed_preview: 'text-cyan-300',
  upsert: 'text-emerald-200',
  upsert_error: 'text-red-300',
  debug_source_start: 'text-violet-300',
  debug_source_done: 'text-violet-200',
  debug_source_unknown: 'text-red-400',
  trigger_skipped: 'text-amber-300',
  bolha_progressive_tick: 'text-fuchsia-300',
  bolha_scout_done: 'text-sky-300',
}

function fmtTs(ts: number): string {
  const d = new Date(ts * 1000)
  return (
    d.toLocaleTimeString([], { hour12: false }) +
    '.' +
    d.getMilliseconds().toString().padStart(3, '0')
  )
}

function eventMatchesSource(ev: ScraperEvent, sourceName: string): boolean {
  if (ev.source === sourceName) return true
  if (
    ev.kind === 'debug_source_unknown' &&
    typeof ev.data?.source === 'string' &&
    ev.data.source === sourceName
  ) {
    return true
  }
  if (
    ev.kind === 'trigger_skipped' &&
    typeof ev.data?.requested_source === 'string' &&
    ev.data.requested_source === sourceName
  ) {
    return true
  }
  if (
    ev.kind === 'bolha_progressive_tick' &&
    sourceName === 'bolha.com' &&
    (ev.source === 'bolha.lookahead' ||
      ev.source === 'bolha.backfill' ||
      ev.source === 'bolha.scout')
  ) {
    return true
  }
  if (ev.kind === 'bolha_scout_done' && sourceName === 'bolha.com') {
    return true
  }
  return false
}

function eventLabel(ev: ScraperEvent): string {
  if (ev.message) return ev.message
  if (ev.data && Object.keys(ev.data).length > 0) {
    return JSON.stringify(ev.data)
  }
  return ev.kind
}

type AdminSourceDebugScrapeProps = {
  sourceName: string
  title: string
  children: ReactNode
  prependSlot?: ReactNode | ((ctx: { live: ScraperLive }) => ReactNode)
}

export function AdminSourceDebugScrape({
  sourceName,
  title,
  children,
  prependSlot,
}: AdminSourceDebugScrapeProps) {
  const live = useScraperLive(true)
  const runSource = useRunSourceScrape()

  const scraperConnected = Boolean(live.status?.connected)
  const runError = runSource.error ? getErrorMessage(runSource.error) : null

  const events = useMemo(() => {
    return live.events
      .filter((ev) => eventMatchesSource(ev, sourceName))
      .slice()
      .reverse()
  }, [live.events, sourceName])

  const onScrapeOnce = () => {
    live.clearEvents()
    runSource.mutate(sourceName)
  }

  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      </header>

      {prependSlot != null && (
        <div className="mb-6">
          {typeof prependSlot === 'function' ? prependSlot({ live }) : prependSlot}
        </div>
      )}

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            How this scrape works
          </h2>
          <div className="space-y-3 text-sm leading-relaxed text-zinc-300">{children}</div>
          <div className="mt-4 rounded-lg border border-zinc-800 bg-black/30 p-3 text-xs text-zinc-400">
            <p className="font-medium text-zinc-300">Live log</p>
            <p className="mt-1">
              The worker runs in a separate process. This page listens on the same admin WebSocket
              and shows only events tagged with <code className="text-zinc-200">{sourceName}</code>{' '}
              (plus “skipped” notices if you queue a run while another scrape is already running).
              HTTP hooks emit one line per request and response so you can see redirects and status
              codes in order.
            </p>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Run once
          </h2>
          <p className="mb-4 text-sm text-zinc-400">
            Sends a <code className="text-zinc-200">run_source</code> command to the worker. It runs
            a single pass for this source with extra debug events (empty-parse hint, parsed row
            preview when items exist). The scheduler and full-cycle trigger are unchanged.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={onScrapeOnce}
              loading={runSource.isPending}
              disabled={!scraperConnected}
            >
              {scraperConnected ? 'Scrape once' : 'Worker offline'}
            </Button>
            <span
              className={`text-xs ${live.socketConnected ? 'text-emerald-400' : 'text-amber-400'}`}
            >
              {live.socketConnected ? 'log stream connected' : 'log stream reconnecting…'}
            </span>
          </div>
          {runError && <p className="mt-2 text-xs text-red-400">{runError}</p>}
          {runSource.isSuccess && !runSource.isPending && (
            <p className="mt-2 text-xs text-zinc-500">Command queued — watch the log below.</p>
          )}
        </Card>
      </div>

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Debug log ({sourceName})
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-500">{events.length} lines</span>
            <button
              type="button"
              onClick={live.clearEvents}
              disabled={events.length === 0}
              className="rounded-md border border-zinc-700 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
            >
              Clear
            </button>
          </div>
        </div>
        <div className="max-h-[min(520px,55vh)] overflow-y-auto rounded-lg border border-zinc-800 bg-black/40 font-mono text-xs">
          {events.length === 0 ? (
            <p className="p-4 text-zinc-500">
              No events for this source yet. Connect the worker, then press “Scrape once”, or wait
              for the scheduled job.
            </p>
          ) : (
            <ul className="divide-y divide-zinc-900">
              {events.map((ev) => (
                <li key={ev.id} className="px-3 py-2">
                  <div className="flex flex-wrap gap-x-3 gap-y-1">
                    <span className="shrink-0 text-zinc-500">{fmtTs(ev.ts)}</span>
                    <span
                      className={`shrink-0 font-semibold ${KIND_COLORS[ev.kind] || 'text-zinc-300'}`}
                    >
                      {ev.kind}
                    </span>
                    <span className="min-w-0 flex-1 wrap-break-word text-zinc-200">
                      {eventLabel(ev)}
                    </span>
                  </div>
                  {ev.kind === 'parsed_preview' &&
                    ev.data &&
                    Array.isArray(ev.data.items) &&
                    ev.data.items.length > 0 && (
                      <pre className="mt-2 max-h-48 overflow-auto rounded border border-zinc-800/80 bg-zinc-950/80 p-2 text-[11px] leading-snug text-zinc-400">
                        {JSON.stringify(ev.data.items, null, 2)}
                      </pre>
                    )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </>
  )
}
