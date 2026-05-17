import { Fragment, useEffect, useState } from 'react'

import {
  bolhaAdUrl,
  BOLHA_ADS_TOP_LIMIT,
  useBolhaAds,
  useBolhaAdsWsSync,
  useBolhaPivotFromWs,
  useMatchBolhaAd,
  useScraperLive,
  type BolhaAdRow,
  type BolhaAdScrapeEntry,
} from '../lib/admin'
import { getErrorMessage } from '../lib/auth'
import { discoveryLagTitle, formatDiscoveryLag } from '../lib/formatLag'
import { Button, Card, TableFrame } from './ui'

const SCRAPE_TIMELINE_WIDTH_PX = 384
const SCRAPE_TIMELINE_TICK_MS = 200

const TIMELINE_WINDOWS = [
  { id: '1m', label: '1m', ms: 60_000 },
  { id: '30m', label: '30m', ms: 30 * 60_000 },
  { id: '2h', label: '2h', ms: 2 * 60 * 60_000 },
] as const

type TimelineWindowId = (typeof TIMELINE_WINDOWS)[number]['id']

function timelineWindowMs(id: TimelineWindowId): number {
  return TIMELINE_WINDOWS.find((w) => w.id === id)?.ms ?? 60_000
}

function timelinePastLabel(ms: number): string {
  if (ms < 60_000) return `−${Math.round(ms / 1000)}s`
  if (ms < 3_600_000) return `−${Math.round(ms / 60_000)}m`
  return `−${Math.round(ms / 3_600_000)}h`
}

function latestScrapeResult(scrapes: BolhaAdScrapeEntry[]): string | null {
  let latest: BolhaAdScrapeEntry | null = null
  let latestAt = -Infinity
  for (const s of scrapes) {
    const t = Date.parse(s.at)
    if (Number.isNaN(t) || t < latestAt) continue
    latestAt = t
    latest = s
  }
  return latest?.result ?? null
}

function statusLabel(row: BolhaAdRow): string {
  const latest = latestScrapeResult(row.scrapes)
  if (latest === 'empty' || latest === 'error') return latest
  return row.status
}

function statusTone(row: BolhaAdRow): string {
  const latest = latestScrapeResult(row.scrapes)
  if (latest === 'empty') {
    return 'bg-yellow-50 text-yellow-800 ring-yellow-200'
  }
  if (latest === 'error') {
    return 'bg-red-50 text-red-800 ring-red-200'
  }
  switch (row.status) {
    case 'pending':
      return 'bg-amber-50 text-amber-800 ring-amber-200'
    case 'empty':
      return 'bg-yellow-50 text-yellow-800 ring-yellow-200'
    case 'backfill':
      return 'bg-sky-50 text-sky-800 ring-sky-200'
    case 'success':
      return 'bg-emerald-50 text-emerald-800 ring-emerald-200'
    case 'timed_out':
      return 'bg-zinc-200 text-zinc-700 ring-zinc-400'
    case 'removed':
      return 'bg-rose-50 text-rose-800 ring-rose-200'
    default:
      return 'bg-zinc-100 text-zinc-600 ring-zinc-300'
  }
}

function scrapeSquareFill(result: string): string {
  switch (result) {
    case 'success':
      return 'bg-emerald-500'
    case 'empty':
      return 'bg-yellow-500'
    case 'removed':
      return 'bg-rose-500'
    case 'error':
      return 'bg-red-500'
    default:
      return 'bg-zinc-400'
  }
}

function fmtOffset(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function fmtAt(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return iso
  }
}

function scrapeTooltip(s: BolhaAdScrapeEntry): string {
  const parts = [fmtAt(s.at), fmtOffset(s.offset_seconds), s.result, s.source.replace('bolha.', '')]
  if (s.http_status != null) parts.push(`HTTP ${s.http_status}`)
  if (s.detail) parts.push(s.detail)
  return parts.join(' · ')
}

function useTimelineNow(tickMs = SCRAPE_TIMELINE_TICK_MS): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), tickMs)
    return () => window.clearInterval(id)
  }, [tickMs])
  return now
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

function rowClassName(highlight: RowHighlight, row: BolhaAdRow): string {
  if (highlight === 'last-id') {
    return 'bg-indigo-500/15 ring-1 ring-inset ring-indigo-400/50'
  }
  if (highlight === 'lookahead') {
    return 'bg-sky-500/10 ring-1 ring-inset ring-sky-500/35'
  }
  if (row.status === 'backfill') {
    return 'bg-sky-50/70 hover:bg-sky-50'
  }
  if (row.status === 'timed_out') {
    return 'bg-zinc-100/80 hover:bg-zinc-100'
  }
  const latest = latestScrapeResult(row.scrapes)
  if (latest === 'empty' || row.status === 'empty') {
    return 'bg-yellow-50/80 hover:bg-yellow-50'
  }
  if (latest === 'error') {
    return 'bg-red-50/80 hover:bg-red-50'
  }
  return 'hover:bg-zinc-50'
}

function timelineNodeClassName(highlight: RowHighlight): string {
  if (highlight === 'last-id') {
    return 'relative z-10 mx-auto block size-2 rounded-full bg-indigo-400 ring-2 ring-white'
  }
  if (highlight === 'lookahead') {
    return 'relative z-10 mx-auto block size-2 rounded-full bg-sky-400/90 ring-2 ring-white'
  }
  return 'relative z-10 mx-auto block size-2 rounded-full bg-zinc-500 ring-2 ring-white'
}

function timelineRailClassName(): string {
  return 'pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-zinc-300'
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
      ? 'bg-zinc-100 ring-zinc-300'
      : severity === 'medium'
        ? 'bg-amber-50 ring-amber-300'
        : 'bg-orange-50 ring-orange-300'

  const ink =
    severity === 'small'
      ? 'text-zinc-500'
      : severity === 'medium'
        ? 'text-amber-600'
        : 'text-orange-600'

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
      <td colSpan={5} className="px-2 py-0 align-middle">
        <span className={`font-mono text-[10px] tabular-nums ${gapCountTextTone(severity)}`}>
          {count === 1 ? '1 ID missing' : `${count.toLocaleString()} IDs missing`}
        </span>
      </td>
    </tr>
  )
}

function AdDataRow({
  row,
  highlight,
  now,
  windowMs,
  onMatch,
  matchLoading,
  matchResult,
  matchError,
}: {
  row: BolhaAdRow
  highlight: RowHighlight
  now: number
  windowMs: number
  onMatch?: (adId: number) => void
  matchLoading?: boolean
  matchResult?: string | null
  matchError?: string | null
}) {
  return (
    <tr className={rowClassName(highlight, row)}>
      <TimelineNode highlight={highlight} />
      <td className="whitespace-nowrap px-2 py-1.5">
        <a
          href={bolhaAdUrl(row.ad_id)}
          target="_blank"
          rel="noreferrer noopener"
          className="font-semibold text-indigo-600 hover:underline"
        >
          {row.ad_id}
        </a>
      </td>
      <td className="px-2 py-1.5">
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ${statusTone(row)}`}
        >
          {statusLabel(row)}
        </span>
      </td>
      <td className="px-2 py-1.5">
        <ScrapeLogTimeline scrapes={row.scrapes} now={now} windowMs={windowMs} />
      </td>
      <td className="whitespace-nowrap px-2 py-1.5 text-right text-zinc-500">
        {row.status === 'success' ? (
          <DiscoveryLag
            publishedAt={row.listing_published_at}
            createdAt={row.listing_created_at}
          />
        ) : (
          <span className="text-zinc-300">—</span>
        )}
      </td>
      <td className="whitespace-nowrap px-2 py-1.5 text-right">
        {row.status === 'success' && onMatch ? (
          <div className="flex flex-col items-end gap-0.5">
            <Button
              type="button"
              variant="ghost"
              className="px-2 py-1 text-[10px] font-medium"
              loading={matchLoading}
              onClick={() => onMatch(row.ad_id)}
            >
              Match
            </Button>
            {matchError ? (
              <span className="max-w-[8rem] truncate text-[10px] text-red-600" title={matchError}>
                {matchError}
              </span>
            ) : matchResult ? (
              <span className="text-[10px] text-emerald-700">{matchResult}</span>
            ) : null}
          </div>
        ) : (
          <span className="text-zinc-300">—</span>
        )}
      </td>
    </tr>
  )
}

function DiscoveryLag({
  publishedAt,
  createdAt,
}: {
  publishedAt?: string | null
  createdAt?: string | null
}) {
  const label = formatDiscoveryLag(publishedAt, createdAt)
  if (!label) return <span className="text-zinc-300">—</span>
  return (
    <span
      className="tabular-nums text-emerald-700"
      title={discoveryLagTitle(publishedAt, createdAt)}
    >
      {label}
    </span>
  )
}

function ScrapeLogTimeline({
  scrapes,
  now,
  windowMs,
}: {
  scrapes: BolhaAdScrapeEntry[]
  now: number
  windowMs: number
}) {
  const dots = scrapes
    .map((s, index) => {
      const t = Date.parse(s.at)
      if (Number.isNaN(t)) return null
      const age = now - t
      if (age < 0 || age > windowMs) return null
      return { s, t, index, age }
    })
    .filter((d): d is NonNullable<typeof d> => d != null)

  const windowLabel = timelinePastLabel(windowMs).slice(1)

  return (
    <div
      className="relative h-6 shrink-0 rounded bg-zinc-100 ring-1 ring-zinc-200"
      style={{ width: SCRAPE_TIMELINE_WIDTH_PX }}
      role="img"
      aria-label={`Scrape attempts in the last ${windowLabel}; now on the right`}
    >
      <span className="pointer-events-none absolute inset-x-1 top-1/2 h-px -translate-y-1/2 bg-zinc-300" />
      <span
        className="pointer-events-none absolute top-1/2 h-2 w-px -translate-y-1/2 bg-zinc-600"
        style={{ left: '50%' }}
        aria-hidden
      />
      <span
        className="pointer-events-none absolute right-0 top-0 bottom-0 w-px bg-indigo-400/90 shadow-[0_0_6px_rgba(129,140,248,0.45)]"
        aria-hidden
      />

      {dots.map(({ s, t, index, age }) => {
        const leftPct = (1 - age / windowMs) * 100
        const lane = index % 3
        const yOffset = lane === 0 ? -3 : lane === 1 ? 0 : 3
        return (
          <span
            key={`${t}-${index}`}
            className="absolute top-1/2 transition-[left] duration-200 ease-linear"
            style={{ left: `${leftPct}%` }}
          >
            <span
              title={scrapeTooltip(s)}
              className={`block size-2 -translate-x-1/2 rounded-full ${scrapeSquareFill(s.result)} ring-1 ring-white/50`}
              style={{ marginTop: yOffset - 4 }}
            />
          </span>
        )
      })}
    </div>
  )
}

type BolhaAdsTableProps = {
  enabled: boolean
  limit?: number
}

export function BolhaAdsTable({ enabled, limit = BOLHA_ADS_TOP_LIMIT }: BolhaAdsTableProps) {
  const q = useBolhaAds(enabled, limit)
  const live = useScraperLive(enabled)
  const pivot = useBolhaPivotFromWs(enabled, live.events)
  useBolhaAdsWsSync(enabled, limit, live.events, q.isSuccess, live.socketConnected)
  const matchBolha = useMatchBolhaAd()

  const [timelineWindow, setTimelineWindow] = useState<TimelineWindowId>('1m')
  const [matchingAdId, setMatchingAdId] = useState<number | null>(null)
  const [matchFeedback, setMatchFeedback] = useState<
    Record<number, { ok?: string; err?: string }>
  >({})

  const runMatch = (adId: number) => {
    setMatchingAdId(adId)
    setMatchFeedback((prev) => {
      const next = { ...prev }
      delete next[adId]
      return next
    })
    matchBolha.mutate(adId, {
      onSuccess: (data) => {
        const n = data.matches_created
        setMatchFeedback((prev) => ({
          ...prev,
          [adId]: {
            ok:
              n === 0 ? '0 matches' : n === 1 ? '1 match' : `${n} matches`,
          },
        }))
      },
      onError: (err) => {
        setMatchFeedback((prev) => ({
          ...prev,
          [adId]: { err: getErrorMessage(err) },
        }))
      },
      onSettled: () => setMatchingAdId(null),
    })
  }
  const windowMs = timelineWindowMs(timelineWindow)
  const timelineNow = useTimelineNow()
  const { lastWorkingId, scanAnchorId, lookaheadCount } = pivot

  if (!enabled) return null

  return (
    <Card>
      <div className="mb-3 flex flex-col gap-1 border-b border-zinc-200 pb-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            bolha_ads
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Top {limit} highest <code className="text-zinc-400">ad_id</code> values. Initial HTTP load,
            then each scrape pushes over the scraper WebSocket. Scrape log timeline (now on the right).
          </p>
        </div>
        <p className="text-xs text-zinc-500">
          {live.socketConnected ? (
            <span className="mr-2 inline-flex items-center gap-1 text-emerald-400/90">
              <span className="size-1.5 rounded-full bg-emerald-400" aria-hidden />
              live
            </span>
          ) : null}
          {q.isFetching && !q.isLoading ? 'Syncing… ' : null}
          <span className="font-mono text-zinc-700">
            {q.data == null ? '…' : `${q.data.length} rows`}
          </span>
        </p>
      </div>

      {q.error && (
        <p className="mb-4 text-sm text-red-600">
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
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-zinc-500">
            <span className="inline-flex items-center gap-2">
              <span className="uppercase tracking-wide">Scrape log</span>
              <span
                className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50/80 p-0.5"
                role="group"
                aria-label="Timeline window"
              >
                {TIMELINE_WINDOWS.map((w) => (
                  <button
                    key={w.id}
                    type="button"
                    onClick={() => setTimelineWindow(w.id)}
                    className={`rounded-md px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors ${
                      timelineWindow === w.id
                        ? 'bg-zinc-300 text-zinc-900'
                        : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700'
                    }`}
                    aria-pressed={timelineWindow === w.id}
                  >
                    {w.label}
                  </button>
                ))}
              </span>
            </span>
            <span className="inline-flex items-center gap-1 font-mono text-zinc-600">
              {timelinePastLabel(windowMs)}
              <span
                className="relative inline-block h-1.5 w-16 rounded-sm bg-zinc-200 ring-1 ring-zinc-300"
                aria-hidden
              >
                <span className="absolute right-0 top-0 bottom-0 w-px bg-indigo-400/80" />
              </span>
              now
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-sky-500" /> backfill
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-emerald-500" /> success
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-zinc-400" /> timed out
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2.5 rounded-sm bg-yellow-500" /> empty (no ad)
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

          <TableFrame>
            <table className="min-w-full divide-y divide-zinc-200 text-left text-xs">
              <thead className="bg-zinc-100 text-[10px] uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="w-7 px-0 py-2" aria-label="Timeline" />
                  <th className="px-2 py-2 font-medium">ad_id</th>
                  <th className="px-2 py-2 font-medium">status</th>
                  <th className="px-2 py-2 font-medium" style={{ width: SCRAPE_TIMELINE_WIDTH_PX }}>
                    scrape log
                  </th>
                  <th className="px-2 py-2 font-medium text-right">lag</th>
                  <th className="px-2 py-2 font-medium text-right">matcher</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 font-mono text-[11px] text-zinc-700">
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
                      <AdDataRow
                        row={row}
                        highlight={highlight}
                        now={timelineNow}
                        windowMs={windowMs}
                        onMatch={runMatch}
                        matchLoading={matchingAdId === row.ad_id && matchBolha.isPending}
                        matchResult={matchFeedback[row.ad_id]?.ok ?? null}
                        matchError={matchFeedback[row.ad_id]?.err ?? null}
                      />
                      {showGap ? <IdGapRow upperId={row.ad_id} lowerId={next.ad_id} /> : null}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </TableFrame>
        </>
      )}
    </Card>
  )
}
