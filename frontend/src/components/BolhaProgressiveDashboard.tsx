import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  adminKeys,
  type BolhaProgressiveRow,
  type BolhaProgressiveState,
  type ScraperEvent,
  useBolhaProgressiveState,
} from '../lib/admin'
import { Card } from './ui'

function statusPill(status: string): string {
  switch (status) {
    case 'successful':
      return 'bg-emerald-50 text-emerald-800 ring-emerald-200'
    case 'not_yet_created':
      return 'bg-zinc-100 text-zinc-700 ring-zinc-300'
    case 'expired':
      return 'bg-rose-50 text-rose-800 ring-rose-200'
    case 'in_progress':
      return 'bg-amber-50 text-amber-800 ring-amber-200'
    case 'timed_out':
      return 'bg-orange-50 text-orange-800 ring-orange-200'
    case 'inactive':
      return 'bg-zinc-100 text-zinc-600 ring-zinc-300'
    case 'error':
      return 'bg-red-50 text-red-800 ring-red-200'
    default:
      return 'bg-zinc-100 text-zinc-500 ring-zinc-300'
  }
}

function fmtWhen(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function ProbeTable({
  title,
  rows,
  highlightAdId,
}: {
  title: string
  rows: BolhaProgressiveRow[]
  highlightAdId: number | null
}) {
  return (
    <div className="mb-6">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">{title}</h3>
      <div className="overflow-x-auto rounded-lg border border-zinc-200">
        <table className="min-w-full divide-y divide-zinc-200 text-left text-xs">
          <thead className="bg-zinc-100 text-[10px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-2 py-2 font-medium">Ad ID</th>
              <th className="px-2 py-2 font-medium">Status</th>
              <th className="px-2 py-2 font-medium">Outcome</th>
              <th className="px-2 py-2 font-medium">HTTP</th>
              <th className="px-2 py-2 font-medium">GTM adStatus</th>
              <th className="px-2 py-2 font-medium">Last fetch</th>
              <th className="px-2 py-2 font-medium">Inactive age (s)</th>
              <th className="px-2 py-2 font-medium">Pipeline</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 font-mono text-[11px] text-zinc-700">
            {rows.map((r) => {
              const hi = highlightAdId != null && r.ad_id === highlightAdId
              return (
                <tr
                  key={`${r.zone}-${r.ad_id}`}
                  className={
                    hi
                      ? 'bg-indigo-500/15 ring-1 ring-inset ring-indigo-400/50'
                      : 'hover:bg-zinc-50'
                  }
                >
                  <td className="px-2 py-1.5 text-zinc-900">{r.ad_id}</td>
                  <td className="px-2 py-1.5">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${statusPill(r.display_status)}`}
                    >
                      {r.display_status}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-zinc-400">{r.outcome ?? '—'}</td>
                  <td className="px-2 py-1.5">{r.http_status ?? '—'}</td>
                  <td className="max-w-[120px] truncate px-2 py-1.5 text-zinc-400">
                    {r.gtm_ad_status ?? '—'}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 text-zinc-500">{fmtWhen(r.fetched_at)}</td>
                  <td className="px-2 py-1.5 text-zinc-500">
                    {r.inactive_age_seconds != null ? r.inactive_age_seconds : '—'}
                  </td>
                  <td className="max-w-[100px] truncate px-2 py-1.5 text-zinc-500">
                    {r.pipeline_status ?? '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

type BolhaProgressiveDashboardProps = {
  enabled: boolean
  liveEvents: ScraperEvent[]
}

export function BolhaProgressiveDashboard({ enabled, liveEvents }: BolhaProgressiveDashboardProps) {
  const qc = useQueryClient()
  const progressive = useBolhaProgressiveState(enabled)
  const lastTickId = useRef<string | null>(null)

  const last = liveEvents[liveEvents.length - 1]
  useEffect(() => {
    if (
      !last ||
      (last.kind !== 'bolha_progressive_tick' && last.kind !== 'bolha_scout_done')
    ) {
      return
    }
    if (last.id === lastTickId.current) return
    lastTickId.current = last.id
    void qc.invalidateQueries({ queryKey: adminKeys.bolhaProgressive })
    void qc.invalidateQueries({ queryKey: adminKeys.bolhaAdStates })
  }, [last, qc])

  if (!enabled) return null

  const d: BolhaProgressiveState | undefined = progressive.data
  const lw = d?.last_working_ad_id ?? 0
  const highlightId = lw > 0 ? lw : d?.scan_anchor_ad_id ?? null

  return (
    <Card className="mb-6">
      <div className="mb-4 flex flex-col gap-2 border-b border-zinc-200 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Progressive cycle
          </h2>
          <p className="mt-1 text-3xl font-semibold tracking-tight text-indigo-600">
            {lw > 0 ? lw : '—'}
            <span className="ml-2 text-sm font-normal text-zinc-500">
              {lw > 0 ? 'last confirmed id (active or expired)' : 'no confirmed id stored yet'}
            </span>
          </p>
          {d?.last_working_at && (
            <p className="text-xs text-zinc-500">Last confirmed at {fmtWhen(d.last_working_at)}</p>
          )}
        </div>
        <div className="text-right text-xs text-zinc-500">
          <p>
            Scan anchor max(hp, high-water, db):{' '}
            <span className="font-mono text-zinc-700">{d?.scan_anchor_ad_id ?? '—'}</span>
          </p>
          <p>
            Homepage max:{' '}
            <span className="font-mono text-zinc-700">{d?.last_homepage_max ?? '—'}</span> · DB
            max: <span className="font-mono text-zinc-700">{d?.db_numeric_max ?? '—'}</span>
          </p>
          <p>
            LOOKAHEAD_ADS:{' '}
            <span className="font-mono text-zinc-700">{d?.look_ahead_count ?? '—'}</span>
          </p>
          {progressive.isFetching && (
            <p className="mt-1 text-indigo-600/80">Refreshing…</p>
          )}
        </div>
      </div>

      {progressive.error && (
        <p className="mb-4 text-sm text-red-600">
          Failed to load progressive state (is the latest migration applied?).
        </p>
      )}

      {d && (
        <>
          <ProbeTable
            title={`Lookahead window (${d.look_ahead_count} ids after pivot)`}
            rows={d.lookahead_rows}
            highlightAdId={null}
          />
          <ProbeTable
            title={
              lw > 0
                ? 'Last confirmed id (drives the rolling +N window)'
                : 'Scan anchor id (no published “last active” yet — matches high-water)'
            }
            rows={[d.pivot_row]}
            highlightAdId={highlightId}
          />
          <ProbeTable
            title="Next 100 ids after pivot (tail)"
            rows={d.tail_rows}
            highlightAdId={null}
          />
        </>
      )}

      {!d && !progressive.isLoading && (
        <p className="text-sm text-zinc-500">
          No progressive data yet. Run a bolha scrape once the worker is connected.
        </p>
      )}
    </Card>
  )
}
