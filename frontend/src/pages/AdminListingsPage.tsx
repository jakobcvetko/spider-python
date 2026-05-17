import { AdminListingsTable } from '../components/AdminListingsTable'
import { AVTONET_LISTING_SOURCE, BOLHA_LISTING_SOURCE } from '../lib/admin'

export default function AdminListingsPage() {
  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Listings</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Latest scraped listings from Bolha and Avto.net (100 per source).
        </p>
      </header>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Bolha
        </h2>
        <AdminListingsTable source={BOLHA_LISTING_SOURCE} />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Avto.net
        </h2>
        <AdminListingsTable source={AVTONET_LISTING_SOURCE} />
      </section>
    </>
  )
}
