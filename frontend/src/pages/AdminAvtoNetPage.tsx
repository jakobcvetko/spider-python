import { AvtonetAdsTable } from '../components/AvtonetAdsTable'

export default function AdminAvtoNetPage() {
  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">avtonet_ads</h1>
      </header>

      <p className="mb-3 text-sm text-zinc-400">
        Live view of ads scraped in the last minute (up to 200 highest ad IDs). Status:{' '}
        <span className="text-amber-700">pending</span> (empty slot),{' '}
        <span className="text-emerald-700">success</span> (listing stored),{' '}
        <span className="text-zinc-400">removed</span> (gone / redirect),{' '}
        <span className="text-sky-700">not_yet_created</span> (no listing yet).
      </p>

      <AvtonetAdsTable enabled />
    </>
  )
}
