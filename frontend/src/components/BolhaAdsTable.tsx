import { Fragment, useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import {
  adminKeys,
  bolhaAdUrl,
  BOLHA_ADS_TOP_LIMIT,
  useBolhaAds,
  useBolhaProgressiveState,
  useScraperLive,
  type BolhaAdRow,
  type BolhaAdScrapeEntry,
} from '../lib/admin'
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

function scrapeSquareFill(result: string): string {
  switch (result) {
    case 'success':
      return 'bg-emerald-500'
    case 'empty':
      return 'bg-amber-500'
    case 'removed':
      return 'bg-rose-500'
    case 'error':
      return 'bg-red-500'
    default:
      return 'bg-zinc-600'
  }
}

function fmtOffset(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function scrapeTooltip(s: BolhaAdScrapeEntry): string {
  const parts = [
    fmtOffset(s.offset_seconds),
    s.result,
    s.source.replace('bolha.', ''),
  ]
  if (s.http_status != null) parts.push(`HTTP ${s.http_status}`)
  if (s.detail) parts.push(s.detail)
  return parts.join(' · ')
}

function idGapCount(upperId: number, lowerId: number): number {
  return upperId - lowerId - 1
}

type GapSeverity = 'small' | 'medium' | 'large'

function gapSeverity(count: number): GapSeverity {
  if (count < 10) return 'small'
  if (count <= 100) return 'medium'
  return 'large'
}

function gapCountTextTone(severity: GapSeverity): string {
  switch (severity) {
    case 'small':
      return 'text-zinc-500'
    case 'medium':
      return 'text-amber-500/90'
    case 'large':
      return 'text-orange-400/90'
  }
}

function idGapTitle(upperId: number, lowerId: number): string {
  const count = idGapCount(upperId, lowerId)
  if (count <= 0) return ''
  const first = lowerId + 1
  const last = upperId - 1
  const range = count === 1 ? `${first}` : `${first}–${last}`
  return `${count} ID${count === 1 ? '' : 's'} missing (${range}) between ${upperId} and ${lowerId}`
}

type RowHighlight = 'last-id' | 'lookahead' | null

function adRowHighlight(
  adId: number,
  lastWorkingId: number,
  scanAnchorId: number,
  lookaheadCount: number,
): RowHighlight {
  const pivot = lastWorkingId > 0 ? lastWorkingId : scanAnchorId
  if (pivot <= 0) return null
  if (adId === pivot) return 'last-id'
  if (adId > pivot && adId <= pivot + lookaheadCount) return 'lookahead'
  return null
}

function rowClassName(highlight: RowHighlight): string {
  if (highlight === 'last-id') {
    return 'bg-indigo-500/15 ring-1 ring-inset ring-indigo-400/50'
  }
  if (highlight === 'lookahead') {
    return 'bg-sky-500/10 ring-1 ring-inset ring-sky-500/35'
  }
  return 'hover:bg-zinc-900/50'
}

function timelineNodeClassName(highlight: RowHighlight): string {
  if (highlight === 'last-id') {
    return 'relative z-10 mx-auto block size-2 rounded-full bg-indigo-400 ring-2 ring-indigo-950'
  }
  if (highlight === 'lookahead') {
    return 'relative z-10 mx-auto block size-2 rounded-full bg-sky-400/90 ring-2 ring-sky-950'
  }
  return 'relative z-10 mx-auto block size-2 rounded-full bg-zinc-500 ring-2 ring-zinc-950'
}

function timelineRailClassName(): string {
  return 'pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-zinc-700'
}

function TimelineNode({ highlight }: { highlight: RowHighlight }) {
  return (
    <td className="relative w-7 px-0 py-0 align-middle">
      <span className={timelineRailClassName()} aria-hidden />
      <span className={timelineNodeClassName(highlight)} aria-hidden />
    </td>
  )
}

function GapTimelineIcon({ severity }: { severity: GapSeverity }) {
  const shell =
    severity === 'small'
      ? 'bg-zinc-800 ring-zinc-600/80'
      : severity === 'medium'
        ? 'bg-amber-950 ring-amber-500/50'
        : 'bg-orange-950 ring-orange-500/60'

  const ink =
    severity === 'small'
      ? 'text-zinc-400'
      : severity === 'medium'
        ? 'text-amber-400'
        : 'text-orange-400'

  if (severity === 'small') {
    return (
      <span
        className={`relative z-10 flex size-4 items-center justify-center rounded-full ring-1 ${shell}`}
        aria-hidden
      >
        <svg viewBox="0 0 12 12" className={`size-2.5 ${ink}`} fill="currentColor">
          <circle cx="2" cy="6" r="1" />
          <circle cx="6" cy="6" r="1" />
          <circle cx="10" cy="6" r="1" />
        </svg>
      </span>
    )
  }

  if (severity === 'medium') {
    return (
      <span
        className={`relative z-10 flex size-4 flex-col items-center justify-center gap-px rounded ring-1 ${shell}`}
        aria-hidden
      >
        <svg viewBox="0 0 12 14" className={`size-3 ${ink}`} fill="currentColor">
          <rect x="5" y="0" width="2" height="3" rx="0.5" />
          <circle cx="3" cy="7" r="1" />
          <circle cx="6" cy="7" r="1" />
          <circle cx="9" cy="7" r="1" />
          <rect x="5" y="11" width="2" height="3" rx="0.5" />
        </svg>
      </span>
    )
  }

  return (
    <span
      className={`relative z-10 flex size-4 items-center justify-center rounded ring-1 ${shell}`}
      aria-hidden
    >
      <svg viewBox="0 0 12 12" className={`size-3 ${ink}`} fill="none" stroke="currentColor" strokeWidth="1.25">
        <path d="M3 4l3 2-3 2M7 4l3 2-3 2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  )
}

function IdGapRow({ upperId, lowerId }: { upperId: number; lowerId: number }) {
  const count = idGapCount(upperId, lowerId)
  if (count <= 0) return null

  const severity = gapSeverity(count)
  const title = idGapTitle(upperId, lowerId)

  return (
    <tr className="h-6" aria-label={title} title={title}>
      <td className="relative w-7 px-0 py-0 align-middle">
        <span
          className="pointer-events-none absolute inset-y-0 left-1/2 -translate-x-1/2 border-l border-dashed border-zinc-600"
          aria-hidden
        />
        <div className="relative flex h-6 items-center justify-center">
          <GapTimelineIcon severity={severity} />
        </div>
      </td>
      <td colSpan={4} className="px-2 py-0 align-middle">
        <span className={`font-mono text-[10px] tabular-nums ${gapCountTextTone(severity)}`}>
          {count === 1 ? '1 ID missing' : `${count.toLocaleString()} IDs missing`}
        </span>
      </td>
    </tr>
  )
}

function AdDataRow({ row, highlight }: { row: BolhaAdRow; highlight: RowHighlight }) {
  return (
    <tr className={rowClassName(highlight)}>
      <TimelineNode highlight={highlight} />
      <td className="whitespace-nowrap px-2 py-1.5">
        <a
          href={bolhaAdUrl(row.ad_id)}
          target="_blank"
          rel="noreferrer noopener"
          className="font-semibold text-indigo-300 hover:underline"
        >
          {row.ad_id}
        </a>
      </td>
      <td className="px-2 py-1.5">
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${statusTone(row.status)}`}
        >
          {row.status}
        </span>
      </td>
      <td className="px-2 py-1.5">
        <ScrapeLogStrip scrapes={row.scrapes} />
      </td>
      <td className="whitespace-nowrap px-2 py-1.5 text-right text-zinc-500">{row.scrapes.length}</td>
    </tr>
  )
}

function ScrapeLogStrip({ scrapes }: { scrapes: BolhaAdScrapeEntry[] }) {
  if (scrapes.length === 0) {
    return <span className="text-zinc-600">—</span>
  }

  return (
    <div className="flex flex-wrap items-center gap-0.5" role="list" aria-label="Scrape history">
      {scrapes.map((s, i) => (
        <span
          key={i}
          role="listitem"
          title={scrapeTooltip(s)}
          className={`size-2.5 shrink-0 rounded-sm ${scrapeSquareFill(s.result)} ring-1 ring-zinc-950/40`}
        />
      ))}
    </div>
  )
}

type BolhaAdsTableProps = {
  enabled: boolean
  limit?: number
}

export function BolhaAdsTable({ enabled, limit = BOLHA_ADS_TOP_LIMIT }: BolhaAdsTableProps) {
  const qc = useQueryClient()
  const q = useBolhaAds(enabled, limit)
  const progressive = useBolhaProgressiveState(enabled)
  const live = useScraperLive(enabled)
  const lastTickId = useRef<string | null>(null)

  const lastWorkingId = progressive.data?.last_working_ad_id ?? 0
  const scanAnchorId = progressive.data?.scan_anchor_ad_id ?? 0
  const lookaheadCount = progressive.data?.look_ahead_count ?? 20

  const last = live.events[live.events.length - 1]
  useEffect(() => {
    if (
      !last ||
      (last.kind !== 'bolha_progressive_tick' && last.kind !== 'bolha_scout_done')
    ) {
      return
    }
    if (last.id === lastTickId.current) return
    lastTickId.current = last.id
    void qc.invalidateQueries({ queryKey: adminKeys.bolhaAds })
    void qc.invalidateQueries({ queryKey: adminKeys.bolhaProgressive })
  }, [last, qc])

  if (!enabled) return null

  return (
    <Card>
      <div className="mb-4 flex flex-col gap-1 border-b border-zinc-800 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            bolha_ads
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Top {limit} highest <code className="text-zinc-400">ad_id</code> values. Updates live via
            scraper WebSocket; scrape log squares left→right (hover for details).
          </p>
        </div>
        <p className="text-xs text-zinc-500">
          {live.socketConnected ? (
            <span className="mr-2 inline-flex items-center gap-1 text-emerald-400/90">
              <span className="size-1.5 rounded-full bg-emerald-400" aria-hidden />
              live
            </span>
          ) : null}
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
        <>
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-zinc-500">
            <span className="uppercase tracking-wide">Scrape log</span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-emerald-500" /> success
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-amber-500" /> empty
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-rose-500" /> removed
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-red-500" /> error
            </span>
            <span className="ml-2 uppercase tracking-wide">ID gap</span>
            <span className="inline-flex items-center gap-1" title="Fewer than 10 missing IDs">
              <GapTimelineIcon severity="small" /> &lt;10
            </span>
            <span className="inline-flex items-center gap-1" title="10–100 missing IDs">
              <GapTimelineIcon severity="medium" /> 10–100
            </span>
            <span className="inline-flex items-center gap-1" title="More than 100 missing IDs">
              <GapTimelineIcon severity="large" /> &gt;100
            </span>
            <span className="ml-2 uppercase tracking-wide">Highlight</span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2 rounded-full bg-indigo-400 ring-1 ring-indigo-400/50" />
              last id
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2 rounded-full bg-sky-400/90 ring-1 ring-sky-500/35" />
              lookahead (+{lookaheadCount})
            </span>
          </div>

          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="min-w-full divide-y divide-zinc-800 text-left text-xs">
              <thead className="bg-zinc-900/80 text-[10px] uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="w-7 px-0 py-2" aria-label="Timeline" />
                  <th className="px-2 py-2 font-medium">ad_id</th>
                  <th className="px-2 py-2 font-medium">status</th>
                  <th className="min-w-32 px-2 py-2 font-medium">scrape log</th>
                  <th className="px-2 py-2 font-medium text-right">scrapes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 font-mono text-[11px] text-zinc-300">
                {q.data.map((row, i) => {
                  const next = q.data![i + 1]
                  const showGap = next != null && idGapCount(row.ad_id, next.ad_id) > 0
                  const highlight = adRowHighlight(
                    row.ad_id,
                    lastWorkingId,
                    scanAnchorId,
                    lookaheadCount,
                  )
                  return (
                    <Fragment key={row.ad_id}>
                      <AdDataRow row={row} highlight={highlight} />
                      {showGap ? <IdGapRow upperId={row.ad_id} lowerId={next.ad_id} /> : null}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  )
}
