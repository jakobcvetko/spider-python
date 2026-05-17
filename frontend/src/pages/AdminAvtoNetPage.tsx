import { AvtonetAdsTable } from '../components/AvtonetAdsTable'
import { Card } from '../components/ui'
import { useAvtonetScrapeState } from '../lib/admin'

export default function AdminAvtoNetPage() {
  const state = useAvtonetScrapeState(true)

  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">avtonet_ads</h1>
      </header>

      <p className="mb-3 text-sm text-zinc-400">
        Live view of the highest avto.net ad IDs probed by lookahead. Status:{' '}
        <span className="text-amber-700">pending</span>,{' '}
        <span className="text-emerald-700">success</span> (listing parsed),{' '}
        <span className="text-rose-700">removed</span> (404 / gone).
      </p>

      {state.data && (
        <Card className="mb-4 text-sm text-zinc-600">
          <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Last working id" value={String(state.data.last_working_ad_id || '—')} />
            <Stat label="Batch size" value={String(state.data.lookahead_batch_size)} />
            <Stat label="Probe delay" value={`${state.data.probe_delay_seconds}s`} />
            <Stat label="Fetch" value={state.data.fetch_mode} />
          </dl>
        </Card>
      )}

      <AvtonetAdsTable enabled />
    </>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-zinc-400">{label}</dt>
      <dd className="font-mono text-zinc-800">{value}</dd>
    </div>
  )
}
