import { useMemo } from 'react'

import { Button, Card } from '../components/ui'
import {
  type ScraperEvent,
  useAdminUsers,
  useScraperLive,
  useTriggerScraper,
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
  cycle_start: 'text-violet-300',
  cycle_done: 'text-violet-200',
  heartbeat: 'text-zinc-500',
  worker_started: 'text-emerald-300',
  worker_stopped: 'text-amber-300',
  trigger_skipped: 'text-amber-300',
  debug_source_start: 'text-violet-300',
  debug_source_done: 'text-violet-200',
  debug_source_unknown: 'text-red-400',
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
  const users = useAdminUsers(true)
  const live = useScraperLive(true)
  const trigger = useTriggerScraper()

  const triggerError = trigger.error ? getErrorMessage(trigger.error) : null
  const events = useMemo(() => live.events.slice().reverse(), [live.events])

  const status = live.status
  const scraperConnected = Boolean(status?.connected)

  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Home</h1>
        <p className="mt-1 text-sm text-zinc-400">Scraper status, live events, and users.</p>
      </header>

      <section className="mb-6 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Scraper status
          </h2>

          <div className="mb-4 flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                scraperConnected ? 'bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400/60' : 'bg-zinc-600'
              }`}
              aria-hidden
            />
            <span className="text-sm">
              Worker:{' '}
              <span className={scraperConnected ? 'text-emerald-300' : 'text-zinc-400'}>
                {scraperConnected ? 'connected' : 'offline'}
              </span>
            </span>
          </div>

          <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-xs text-zinc-400">
            <dt>Live socket</dt>
            <dd className={live.socketConnected ? 'text-emerald-300' : 'text-amber-300'}>
              {live.socketConnected ? 'connected' : 'reconnecting…'}
            </dd>
            <dt>Last heartbeat</dt>
            <dd className="text-zinc-200">{fmtAge(status?.seconds_since_heartbeat ?? null)} ago</dd>
            <dt>Interval</dt>
            <dd className="text-zinc-200">{status?.interval_seconds ?? '—'}s</dd>
            <dt>Sources</dt>
            <dd className="text-zinc-200">
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
              <p className="text-xs text-red-400">{triggerError}</p>
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
                className="rounded-md border border-zinc-700 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
              >
                Clear
              </button>
            </div>
          </div>
          <div className="max-h-[420px] overflow-y-auto rounded-lg border border-zinc-800 bg-black/40 font-mono text-xs">
            {events.length === 0 ? (
              <p className="p-4 text-zinc-500">
                Waiting for scraper events…
              </p>
            ) : (
              <ul className="divide-y divide-zinc-900">
                {events.map((ev) => (
                  <li key={ev.id} className="flex gap-3 px-3 py-1.5">
                    <span className="shrink-0 text-zinc-500">{fmtTs(ev.ts)}</span>
                    <span
                      className={`shrink-0 w-32 truncate ${KIND_COLORS[ev.kind] || 'text-zinc-300'}`}
                    >
                      {ev.kind}
                    </span>
                    <span className="shrink-0 w-20 truncate text-zinc-400">
                      {ev.source || '—'}
                    </span>
                    <span className="truncate text-zinc-200">{eventLabel(ev)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </section>

      <Card>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold">Users</h2>
            <p className="text-sm text-zinc-400">
              All registered accounts.
            </p>
          </div>
          {users.isFetching && (
            <span className="text-xs text-zinc-500">Refreshing…</span>
          )}
        </div>

        {users.isLoading ? (
          <p className="text-sm text-zinc-500">Loading users…</p>
        ) : users.error ? (
          <p className="text-sm text-red-400">
            Failed to load users: {getErrorMessage(users.error)}
          </p>
        ) : !users.data || users.data.length === 0 ? (
          <p className="text-sm text-zinc-500">No users yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="min-w-full divide-y divide-zinc-800 text-sm">
              <thead className="bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Email</th>
                  <th className="px-3 py-2 text-left font-medium">Display name</th>
                  <th className="px-3 py-2 text-left font-medium">Role</th>
                  <th className="px-3 py-2 text-left font-medium">Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {users.data.map((u) => (
                  <tr key={u.id} className="hover:bg-zinc-900/40">
                    <td className="px-3 py-2 text-zinc-100">{u.email}</td>
                    <td className="px-3 py-2 text-zinc-300">
                      {u.display_name || <span className="text-zinc-600">—</span>}
                    </td>
                    <td className="px-3 py-2">
                      {u.is_admin ? (
                        <span className="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-indigo-200">
                          admin
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-500">user</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-zinc-400">
                      {new Date(u.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
