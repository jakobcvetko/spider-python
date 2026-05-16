import { Card } from '../components/ui'
import { useAdminListings } from '../lib/admin'
import { getErrorMessage } from '../lib/auth'
import { formatPrice } from '../lib/listings'

export default function AdminListingsPage() {
  const adminListings = useAdminListings(true)

  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Listings</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Last 100: Bolha by ad ID (highest first), then others by time added.
        </p>
      </header>

      <Card>
        <div className="mb-3 flex items-end justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Recent listings
          </h2>
          {adminListings.isFetching && (
            <span className="text-xs text-zinc-500">Refreshing…</span>
          )}
        </div>

        {adminListings.isLoading ? (
          <p className="text-sm text-zinc-500">Loading listings…</p>
        ) : adminListings.error ? (
          <p className="text-sm text-red-400">
            Failed to load listings: {getErrorMessage(adminListings.error)}
          </p>
        ) : !adminListings.data || adminListings.data.length === 0 ? (
          <p className="text-sm text-zinc-500">No listings in the database yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="min-w-full divide-y divide-zinc-800 text-sm">
              <thead className="bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-400">
                <tr>
                  <th className="w-14 px-2 py-2 text-left font-medium" aria-hidden />
                  <th className="px-3 py-2 text-left font-medium">Title</th>
                  <th className="px-3 py-2 text-left font-medium">Source</th>
                  <th className="px-3 py-2 text-left font-medium">Price</th>
                  <th className="px-3 py-2 text-left font-medium">Location</th>
                  <th className="px-3 py-2 text-left font-medium">Year / km</th>
                  <th className="px-3 py-2 text-left font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {adminListings.data.map((row) => (
                  <tr key={row.id} className="hover:bg-zinc-900/40">
                    <td className="px-2 py-1.5 align-middle">
                      {row.image_url ? (
                        <img
                          src={row.image_url}
                          alt=""
                          className="h-10 w-14 rounded object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <span className="block h-10 w-14 rounded bg-zinc-800" />
                      )}
                    </td>
                    <td className="max-w-[min(28rem,40vw)] px-3 py-2 align-middle">
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="line-clamp-2 font-medium text-indigo-300 hover:underline"
                      >
                        {row.title}
                      </a>
                      <div className="mt-0.5 truncate text-[11px] text-zinc-500">
                        {row.external_id}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-300">
                      {row.source}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 align-middle text-zinc-200">
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
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
