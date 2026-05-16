import { BolhaAdsTable } from '../components/BolhaAdsTable'

export default function AdminBolhaPage() {
  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">bolha_ads</h1>
      </header>

      <p className="mb-4 text-sm text-zinc-400">
        Live view of the 200 highest ad IDs probed by lookahead or backfill. Status:{' '}
        <span className="text-amber-200">pending</span> (empty slot),{' '}
        <span className="text-emerald-200">active</span> (listing scraped),{' '}
        <span className="text-zinc-400">inactive</span> (gone / redirect),{' '}
        <span className="text-sky-200">not_yet_created</span> (same URL, no listing yet).
      </p>

      <BolhaAdsTable enabled />
    </>
  )
}
