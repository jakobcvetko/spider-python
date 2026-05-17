import { AdminListingsTable } from '../components/AdminListingsTable'
import { AVTONET_LISTING_SOURCE } from '../lib/admin'

export default function AdminAvtonetListingsPage() {
  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Avtonet listings</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Latest avto.net listings (newest ingested first).
        </p>
      </header>
      <AdminListingsTable source={AVTONET_LISTING_SOURCE} />
    </>
  )
}
