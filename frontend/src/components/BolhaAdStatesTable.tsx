import { useBolhaAdStates } from '../lib/admin'
import { Card } from './ui'

function fmtIso(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function statusTone(status: string): string {
  switch (status) {
    case 'lookahead':
      return 'bg-sky-500/15 text-sky-200 ring-sky-500/35'
    case 'pending_fallback':
      return 'bg-amber-500/15 text-amber-200 ring-amber-500/35'
    case 'fallback_warming':
      return 'bg-violet-500/15 text-violet-200 ring-violet-500/35'
    case 'timed_out':
      return 'bg-orange-500/15 text-orange-200 ring-orange-500/35'
    case 'expired':
      return 'bg-rose-500/15 text-rose-200 ring-rose-500/35'
    default:
      return 'bg-zinc-600/30 text-zinc-300 ring-zinc-500/30'
  }
}

type BolhaAdStatesTableProps = {
  enabled: boolean
}

export function BolhaAdStatesTable({ enabled }: BolhaAdStatesTableProps) {
  const q = useBolhaAdStates(enabled)

  if (!enabled) return null

  return (
    <Card className="mb-6">
      <div className="mb-4 flex flex-col gap-1 border-b border-zinc-800 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            bolha_ad_states
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            All pipeline rows (newest <code className="text-zinc-400">ad_id</code> first), up to
            10&nbsp;000 rows. Refreshes with the progressive panel.
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
          Failed to load ad states (is the latest migration applied?).
        </p>
      )}

      {q.isLoading && <p className="text-sm text-zinc-500">Loading…</p>}

      {!q.isLoading && q.data && q.data.length === 0 && (
        <p className="text-sm text-zinc-500">No rows in bolha_ad_states yet.</p>
      )}

      {!q.isLoading && q.data && q.data.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="min-w-full divide-y divide-zinc-800 text-left text-xs">
            <thead className="bg-zinc-900/80 text-[10px] uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-2 py-2 font-medium">ad_id</th>
                <th className="px-2 py-2 font-medium">status</th>
                <th className="px-2 py-2 font-medium">last_lookahead_at</th>
                <th className="px-2 py-2 font-medium">first_fallback_scrape_at</th>
                <th className="px-2 py-2 font-medium">last_fallback_scrape_at</th>
                <th className="px-2 py-2 font-medium">last_outcome</th>
                <th className="px-2 py-2 font-medium">last_detail</th>
                <th className="px-2 py-2 font-medium">created_at</th>
                <th className="px-2 py-2 font-medium">updated_at</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900 font-mono text-[11px] text-zinc-300">
              {q.data.map((row) => (
                <tr key={row.ad_id} className="hover:bg-zinc-900/50">
                  <td className="whitespace-nowrap px-2 py-1.5 text-zinc-100">{row.ad_id}</td>
                  <td className="px-2 py-1.5">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${statusTone(row.status)}`}
                    >
                      {row.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 text-zinc-500">
                    {fmtIso(row.last_lookahead_at)}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 text-zinc-500">
                    {fmtIso(row.first_fallback_scrape_at)}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 text-zinc-500">
                    {fmtIso(row.last_fallback_scrape_at)}
                  </td>
                  <td className="max-w-[140px] truncate px-2 py-1.5 text-zinc-400" title={row.last_outcome ?? ''}>
                    {row.last_outcome ?? '—'}
                  </td>
                  <td
                    className="max-w-[200px] truncate px-2 py-1.5 text-zinc-500"
                    title={row.last_detail ?? ''}
                  >
                    {row.last_detail ?? '—'}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 text-zinc-500">{fmtIso(row.created_at)}</td>
                  <td className="whitespace-nowrap px-2 py-1.5 text-zinc-500">{fmtIso(row.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
