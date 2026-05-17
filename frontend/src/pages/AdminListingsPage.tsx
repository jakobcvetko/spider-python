import { useState } from 'react'

import {
  AdminListingsTable,
  type ListingSourceFilter,
} from '../components/AdminListingsTable'

export default function AdminListingsPage() {
  const [sourceFilter, setSourceFilter] = useState<ListingSourceFilter>('all')

  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Listings</h1>
        <p className="mt-1 text-sm text-zinc-400">
          All scraped listings from Bolha and Avto.net (up to 500, newest ingested
          first).
        </p>
      </header>

      <AdminListingsTable
        showSourceFilter
        sourceFilter={sourceFilter}
        onSourceFilterChange={setSourceFilter}
      />
    </>
  )
}
