import { AdminListingsTable } from '../components/AdminListingsTable'
import { BOLHA_LISTING_SOURCE } from '../lib/admin'

export default function AdminBolhaListingsPage() {
  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Bolha listings</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Latest 100 bolha.com listings by ad ID (highest first).
        </p>
      </header>
      <AdminListingsTable source={BOLHA_LISTING_SOURCE} />
    </>
  )
}
