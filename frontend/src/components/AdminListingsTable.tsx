import { Card, TableFrame } from './ui'
import { type AdminListing, useAdminListings } from '../lib/admin'
import { getErrorMessage } from '../lib/auth'
import { formatPrice } from '../lib/listings'

type AdminListingsTableProps = {
  source: string
  enabled?: boolean
  limit?: number
}

export function AdminListingsTable({
  source,
  enabled = true,
  limit = 100,
}: AdminListingsTableProps) {
  const listings = useAdminListings(enabled, { source, limit })

  return (
    <Card>
      <div className="mb-3 flex items-end justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Recent listings
        </h2>
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
        <p className="text-sm text-zinc-500">
          No {source} listings in the database yet.
        </p>
      ) : (
        <TableFrame>
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-100 text-xs uppercase tracking-wide text-zinc-400">
              <tr>
                <th className="w-14 px-2 py-2 text-left font-medium" aria-hidden />
                <th className="px-3 py-2 text-left font-medium">Title</th>
                <th className="px-3 py-2 text-left font-medium">Ad ID</th>
                <th className="px-3 py-2 text-left font-medium">Price</th>
                <th className="px-3 py-2 text-left font-medium">Location</th>
                <th className="px-3 py-2 text-left font-medium">Year / km</th>
                <th className="px-3 py-2 text-left font-medium">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {listings.data.map((row) => (
                <ListingRow key={row.id} row={row} />
              ))}
            </tbody>
          </table>
        </TableFrame>
      )}
    </Card>
  )
}

function ListingRow({ row }: { row: AdminListing }) {
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
      <td className="whitespace-nowrap px-3 py-2 align-middle font-mono text-xs text-zinc-600">
        {row.external_id}
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-800">
        {formatPrice(row)}
      </td>
      <td className="max-w-[10rem] truncate px-3 py-2 align-middle text-zinc-400">
        {row.location || '—'}
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-400">
        {row.year != null || row.mileage_km != null ? (
          <>
            {row.year != null && <span>{row.year}</span>}
            {row.year != null && row.mileage_km != null && (
              <span className="text-zinc-600"> · </span>
            )}
            {row.mileage_km != null && (
              <span>{row.mileage_km.toLocaleString()} km</span>
            )}
          </>
        ) : (
          '—'
        )}
      </td>
      <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-400">
        {new Date(row.updated_at).toLocaleString()}
      </td>
    </tr>
  )
}
