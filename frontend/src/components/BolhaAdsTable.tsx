import { useBolhaAds } from '../lib/admin'
import { Card } from './ui'

function statusTone(status: string): string {
  switch (status) {
    case 'pending':
      return 'bg-amber-500/15 text-amber-200 ring-amber-500/35'
    case 'success':
      return 'bg-emerald-500/15 text-emerald-200 ring-emerald-500/35'
    case 'removed':
      return 'bg-rose-500/15 text-rose-200 ring-rose-500/35'
    default:
      return 'bg-zinc-600/30 text-zinc-300 ring-zinc-500/30'
  }
}

function scrapeResultTone(result: string): string {
  switch (result) {
    case 'success':
      return 'text-emerald-300'
    case 'empty':
      return 'text-amber-300'
    case 'removed':
      return 'text-rose-300'
    case 'error':
      return 'text-red-300'
    default:
      return 'text-zinc-400'
  }
}

function fmtOffset(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

type BolhaAdsTableProps = {
  enabled: boolean
  limit?: number
}

export function BolhaAdsTable({ enabled, limit = 500 }: BolhaAdsTableProps) {
  const q = useBolhaAds(enabled, limit)

  if (!enabled) return null

  return (
    <Card>
      <div className="mb-4 flex flex-col gap-1 border-b border-zinc-800 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            bolha_ads
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Every probed ad ID (highest <code className="text-zinc-400">ad_id</code> first). Scrape
            times are seconds since the row was first created.
          </p>
        </div>
        <p className="text-xs text-zinc-500">
          {q.isFetching && !q.isLoading ? 'Refreshing… ' : null}
          <span className="font-mono text-zinc-300">
            {q.data == null ? '…' : `${q.data.length} rows`}
          </span>
        </p>
      </div>

      {q.error && (
        <p className="mb-4 text-sm text-red-400">
          Failed to load bolha ads (is the latest migration applied?).
        </p>
      )}

      {q.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}

      {!q.isLoading && q.data && q.data.length === 0 && (
        <p className="text-sm text-zinc-500">
          No rows in bolha_ads yet — start lookahead or backfill.
        </p>
      )}

      {!q.isLoading && q.data && q.data.length > 0 && (
        <div className="space-y-3">
          {q.data.map((row) => (
            <div
              key={row.ad_id}
              className="flex flex-col gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 sm:flex-row sm:items-start sm:gap-4"
            >
              <div className="shrink-0 sm:w-36">
                <p className="font-mono text-sm font-semibold text-zinc-100">{row.ad_id}</p>
                <span
                  className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${statusTone(row.status)}`}
                >
                  {row.status}
                </span>
                <p className="mt-2 text-[10px] text-zinc-600">
                  {row.scrapes.length} scrape{row.scrapes.length === 1 ? '' : 's'}
                </p>
              </div>
              <div className="min-w-0 flex-1">
                {row.scrapes.length === 0 ? (
                  <p className="text-xs text-zinc-500">No scrape log entries.</p>
                ) : (
                  <ul className="space-y-1 font-mono text-[11px]">
                    {row.scrapes.map((s, i) => (
                      <li key={`${row.ad_id}-${i}`} className="flex flex-wrap items-baseline gap-x-2">
                        <span className="w-14 shrink-0 text-right text-zinc-500">
                          {fmtOffset(s.offset_seconds)}
                        </span>
                        <span className={`font-semibold uppercase ${scrapeResultTone(s.result)}`}>
                          {s.result}
                        </span>
                        <span className="text-zinc-600">{s.source.replace('bolha.', '')}</span>
                        {s.http_status != null && (
                          <span className="text-zinc-600">HTTP {s.http_status}</span>
                        )}
                        {s.detail && (
                          <span className="truncate text-zinc-500" title={s.detail}>
                            {s.detail}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
