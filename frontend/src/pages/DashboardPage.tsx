import { useNavigate } from 'react-router-dom'

import { Button, Card, PageShell } from '../components/ui'
import { useLogout, useMe } from '../lib/auth'
import { formatPrice, useListings } from '../lib/listings'

export default function DashboardPage() {
  const navigate = useNavigate()
  const me = useMe()
  const logout = useLogout()
  const listings = useListings(Boolean(me.data))

  const onLogout = async () => {
    await logout.mutateAsync()
    navigate('/login', { replace: true })
  }

  return (
    <PageShell>
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Spider</h1>
          <p className="text-sm text-zinc-400">
            Signed in as{' '}
            <span className="text-zinc-200">{me.data?.display_name || me.data?.email}</span>
          </p>
        </div>
        <Button variant="ghost" loading={logout.isPending} onClick={onLogout}>
          Sign out
        </Button>
      </header>

      <Card>
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold">Latest scraped listings</h2>
            <p className="text-sm text-zinc-400">
              Auto-refreshes every 30s. The worker scrapes avto.net and bolha.com.
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
            No listings yet. Start the scraper worker (<code>uv run python -m scraper.worker</code>) to begin collecting items.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {listings.data.map((listing) => (
              <li
                key={listing.id}
                className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/40"
              >
                <a
                  href={listing.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="block hover:bg-zinc-900"
                >
                  {listing.image_url && (
                    <img
                      src={listing.image_url}
                      alt=""
                      className="h-36 w-full object-cover"
                      loading="lazy"
                    />
                  )}
                  <div className="p-3">
                    <div className="mb-1 flex items-start justify-between gap-2">
                      <span className="line-clamp-2 text-sm font-medium text-zinc-100">
                        {listing.title}
                      </span>
                      <span className="shrink-0 rounded-full border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-300">
                        {listing.source}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="text-indigo-300">{formatPrice(listing)}</span>
                      <span>
                        {listing.year && <>{listing.year} · </>}
                        {listing.mileage_km != null && <>{listing.mileage_km.toLocaleString()} km</>}
                      </span>
                    </div>
                  </div>
                </a>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </PageShell>
  )
}
