import { Link, useNavigate } from 'react-router-dom'

import { Button, Card, PageShell } from '../components/ui'
import { useLogout, useMe } from '../lib/auth'
import { formatPrice, useListings } from '../lib/listings'

const LISTINGS_LIMIT = 200

export default function ListingsPage() {
  const navigate = useNavigate()
  const me = useMe()
  const logout = useLogout()
  const listings = useListings(Boolean(me.data), LISTINGS_LIMIT)

  const onLogout = async () => {
    await logout.mutateAsync()
    navigate('/login', { replace: true })
  }

  return (
    <PageShell>
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Listings</h1>
          <p className="text-sm text-zinc-400">
            Signed in as{' '}
            <span className="text-zinc-200">{me.data?.display_name || me.data?.email}</span>
            <span className="text-zinc-500"> · </span>
            Bolha ads by ad ID (highest first); then others by time added. Auto-refresh every 30s.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {me.data?.is_admin && (
            <Link
              to="/admin"
              className="rounded-lg px-3 py-2 text-sm font-medium text-indigo-300 hover:bg-zinc-800"
            >
              Admin
            </Link>
          )}
          <Button variant="ghost" loading={logout.isPending} onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </header>

      <Card>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
              Scraped ads
            </h2>
            <p className="text-sm text-zinc-500">
              Up to {LISTINGS_LIMIT} rows from avto.net and bolha.com.
            </p>
          </div>
          {listings.isFetching && (
            <span className="text-xs text-zinc-500">Refreshing…</span>
          )}
        </div>

        {listings.isLoading ? (
          <p className="text-sm text-zinc-500">Loading listings…</p>
        ) : listings.error ? (
          <p className="text-sm text-red-400">Failed to load listings.</p>
        ) : !listings.data || listings.data.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No listings yet. Start a scraper worker (e.g.{' '}
            <code className="text-zinc-300">make bolha:lookahead</code> or{' '}
            <code className="text-zinc-300">make bolha:backfill</code>) to begin collecting items.
          </p>
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
                  <th className="px-3 py-2 text-left font-medium">Added</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {listings.data.map((row) => (
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
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </PageShell>
  )
}
