import { useState } from 'react'

import { Card, Modal, TableFrame } from './ui'
import {
  type AdminListing,
  AVTONET_LISTING_SOURCE,
  BOLHA_LISTING_SOURCE,
  useAdminListingMatches,
  useAdminListings,
} from '../lib/admin'
import { getErrorMessage } from '../lib/auth'
import { discoveryLagTitle, formatDiscoveryLag } from '../lib/formatLag'
import { formatPrice } from '../lib/listings'

export type ListingSourceFilter = 'all' | 'bolha' | 'avtonet'

type AdminListingsTableProps = {
  source?: string
  showSourceFilter?: boolean
  sourceFilter?: ListingSourceFilter
  onSourceFilterChange?: (filter: ListingSourceFilter) => void
  enabled?: boolean
  limit?: number
}

function sourceFilterToParam(filter: ListingSourceFilter): string | undefined {
  if (filter === 'bolha') return BOLHA_LISTING_SOURCE
  if (filter === 'avtonet') return AVTONET_LISTING_SOURCE
  return undefined
}

function formatSourceLabel(source: string): string {
  if (source === BOLHA_LISTING_SOURCE) return 'Bolha'
  if (source === AVTONET_LISTING_SOURCE) return 'Avto.net'
  return source
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function AdminListingsTable({
  source: fixedSource,
  showSourceFilter = false,
  sourceFilter = 'all',
  onSourceFilterChange,
  enabled = true,
  limit = 500,
}: AdminListingsTableProps) {
  const apiSource = fixedSource ?? sourceFilterToParam(sourceFilter)
  const listings = useAdminListings(enabled, { source: apiSource, limit })

  const [matchesListing, setMatchesListing] = useState<AdminListing | null>(null)
  const matchesQuery = useAdminListingMatches(
    matchesListing?.id ?? null,
    !!matchesListing,
  )

  return (
    <Card>
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-2">
          {showSourceFilter && onSourceFilterChange && (
            <SourceFilterBar
              value={sourceFilter}
              onChange={onSourceFilterChange}
            />
          )}
        </div>
        {listings.isFetching && (
          <span className="text-xs text-zinc-500">Refreshing…</span>
        )}
      </div>

      {listings.isLoading ? (
        <p className="text-sm text-zinc-500">Loading listings…</p>
      ) : listings.error ? (
        <p className="text-sm text-red-600">
          Failed to load listings: {getErrorMessage(listings.error)}
        </p>
      ) : !listings.data || listings.data.length === 0 ? (
        <p className="text-sm text-zinc-500">No listings in the database yet.</p>
      ) : (
        <>
          <p className="text-xs text-zinc-500">
            Showing {listings.data.length} listing
            {listings.data.length === 1 ? '' : 's'}
            {apiSource ? ` (${formatSourceLabel(apiSource)})` : ''}
            {listings.data.length >= limit ? ` · capped at ${limit}` : ''}
          </p>
          <TableFrame>
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-100 text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="w-14 px-2 py-2 text-left font-medium" aria-hidden />
                  <th className="px-3 py-2 text-left font-medium">Title</th>
                  {!fixedSource && (
                    <th className="px-3 py-2 text-left font-medium">Source</th>
                  )}
                  <th className="px-3 py-2 text-left font-medium">Ad ID</th>
                  <th className="px-3 py-2 text-left font-medium">Price</th>
                  <th className="px-3 py-2 text-left font-medium">Published</th>
                  <th className="px-3 py-2 text-left font-medium">Ingested</th>
                  <th className="px-3 py-2 text-left font-medium">Scrape lag</th>
                  <th className="px-3 py-2 text-right font-medium">Matches</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {listings.data.map((row) => (
                  <ListingRow
                    key={row.id}
                    row={row}
                    showSourceColumn={!fixedSource}
                    onMatchesClick={() => setMatchesListing(row)}
                  />
                ))}
              </tbody>
            </table>
          </TableFrame>
        </>
      )}

      <Modal
        open={matchesListing !== null}
        onClose={() => setMatchesListing(null)}
        title={
          matchesListing
            ? `Matches · ${matchesListing.title.slice(0, 60)}${matchesListing.title.length > 60 ? '…' : ''}`
            : 'Matches'
        }
      >
        {matchesListing && (
          <MatchesModalBody listing={matchesListing} query={matchesQuery} />
        )}
      </Modal>
    </Card>
  )
}

function SourceFilterBar({
  value,
  onChange,
}: {
  value: ListingSourceFilter
  onChange: (v: ListingSourceFilter) => void
}) {
  const options: { id: ListingSourceFilter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'bolha', label: 'Bolha' },
    { id: 'avtonet', label: 'Avto.net' },
  ]
  return (
    <div className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5">
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onChange(opt.id)}
          className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
            value === opt.id
              ? 'bg-white text-zinc-900 shadow-sm'
              : 'text-zinc-500 hover:text-zinc-800'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function ListingRow({
  row,
  showSourceColumn,
  onMatchesClick,
}: {
  row: AdminListing
  showSourceColumn: boolean
  onMatchesClick: () => void
}) {
  return (
    <tr className="hover:bg-zinc-50">
      <td className="px-2 py-1.5 align-middle">
        {row.image_url ? (
          <img
            src={row.image_url}
            alt=""
            className="h-10 w-14 rounded object-cover"
            loading="lazy"
          />
        ) : (
          <span className="block h-10 w-14 rounded bg-zinc-200" />
        )}
      </td>
      <td className="max-w-[min(28rem,40vw)] px-3 py-2 align-middle">
        <a
          href={row.url}
          target="_blank"
          rel="noreferrer noopener"
          className="line-clamp-2 font-medium text-indigo-600 hover:underline"
        >
          {row.title}
        </a>
      </td>
      {showSourceColumn && (
        <td className="whitespace-nowrap px-3 py-2 align-middle">
          <SourceBadge source={row.source} />
        </td>
      )}
      <td className="whitespace-nowrap px-3 py-2 align-middle font-mono text-xs text-zinc-600">
        {row.external_id}
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-800">
        {formatPrice(row)}
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-500">
        {formatDateTime(row.published_at)}
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-500">
        {formatDateTime(row.created_at)}
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle">
        <DiscoveryLag
          publishedAt={row.published_at}
          createdAt={row.created_at}
        />
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle text-right">
        <button
          type="button"
          onClick={onMatchesClick}
          disabled={row.matches_count === 0}
          className={`tabular-nums font-medium ${
            row.matches_count > 0
              ? 'text-indigo-600 hover:underline'
              : 'cursor-default text-zinc-300'
          }`}
          title={
            row.matches_count > 0
              ? 'Show user scrapers that matched this listing'
              : 'No scraper matches'
          }
        >
          {row.matches_count}
        </button>
      </td>
    </tr>
  )
}

function SourceBadge({ source }: { source: string }) {
  const isBolha = source === BOLHA_LISTING_SOURCE
  return (
    <span
      className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ${
        isBolha ? 'bg-amber-100 text-amber-900' : 'bg-sky-100 text-sky-900'
      }`}
    >
      {formatSourceLabel(source)}
    </span>
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

function MatchesModalBody({
  listing,
  query,
}: {
  listing: AdminListing
  query: ReturnType<typeof useAdminListingMatches>
}) {
  if (query.isLoading) {
    return <p className="text-sm text-zinc-500">Loading matches…</p>
  }
  if (query.error) {
    return (
      <p className="text-sm text-red-600">{getErrorMessage(query.error)}</p>
    )
  }
  if (!query.data || query.data.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No user scrapers matched this listing.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-zinc-500">
        {formatSourceLabel(listing.source)} · ad{' '}
        <span className="font-mono">{listing.external_id}</span>
      </p>
      <ul className="max-h-80 divide-y divide-zinc-100 overflow-y-auto rounded-lg border border-zinc-200">
        {query.data.map((m) => (
          <li key={m.scraper_id} className="px-3 py-2.5">
            <p className="font-medium text-zinc-900">{m.scraper_name}</p>
            <p className="text-xs text-zinc-500">{m.user_email}</p>
            <p className="mt-1 text-xs text-zinc-400">
              {[
                m.bolha_enabled && 'Bolha',
                m.avtonet_enabled && 'Avto.net',
              ]
                .filter(Boolean)
                .join(' · ') || '—'}
              {' · '}
              matched {new Date(m.matched_at).toLocaleString()}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}