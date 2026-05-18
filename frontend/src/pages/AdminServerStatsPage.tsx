import { Button, Card } from '../components/ui'
import { useServerStats, type ServerDisk, type ServerMemory } from '../lib/admin'
import { getErrorMessage } from '../lib/auth'

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KiB', 'MiB', 'GiB', 'TiB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ${units[unit]}`
}

function fmtPercent(value: number): string {
  return `${value.toFixed(1)}%`
}

function fmtUptime(seconds: number): string {
  const days = Math.floor(seconds / 86_400)
  const hours = Math.floor((seconds % 86_400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function UsageBar({ percent }: { percent: number }) {
  const tone =
    percent >= 90 ? 'bg-red-500' : percent >= 75 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-200">
      <div
        className={`h-full rounded-full ${tone}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  )
}

function MemoryCard({ title, memory }: { title: string; memory: ServerMemory }) {
  return (
    <Card>
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">{title}</h2>
        <span className="text-xs text-zinc-500">{memory.scope}</span>
      </div>
      <UsageBar percent={memory.percent} />
      <dl className="mt-3 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-sm">
        <dt className="text-zinc-500">Used</dt>
        <dd className="text-zinc-800">
          {fmtBytes(memory.used_bytes)} / {fmtBytes(memory.total_bytes)} ({fmtPercent(memory.percent)})
        </dd>
        <dt className="text-zinc-500">Available</dt>
        <dd className="text-zinc-800">{fmtBytes(memory.available_bytes)}</dd>
      </dl>
    </Card>
  )
}

function DiskCard({ disk }: { disk: ServerDisk }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white/60 p-3">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-zinc-800">{disk.mountpoint}</h3>
        <span className="text-xs text-zinc-500">{fmtPercent(disk.percent)}</span>
      </div>
      <UsageBar percent={disk.percent} />
      <p className="mt-2 text-xs text-zinc-500">
        {fmtBytes(disk.used_bytes)} used · {fmtBytes(disk.free_bytes)} free · {fmtBytes(disk.total_bytes)} total
      </p>
    </div>
  )
}

export default function AdminServerStatsPage() {
  const stats = useServerStats(true)
  const error = stats.error ? getErrorMessage(stats.error) : null
  const data = stats.data

  return (
    <>
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Server stats</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Host memory, disk, CPU, and database size. Refreshes every 30s.
          </p>
        </div>
        <Button
          variant="ghost"
          onClick={() => void stats.refetch()}
          loading={stats.isFetching && !stats.isLoading}
          disabled={stats.isLoading}
        >
          Refresh now
        </Button>
      </header>

      {error && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {stats.isLoading && !data ? (
        <p className="text-sm text-zinc-500">Loading server stats…</p>
      ) : data ? (
        <>
          <section className="mb-4 grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                System
              </h2>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-sm">
                <dt className="text-zinc-500">Hostname</dt>
                <dd className="font-mono text-xs text-zinc-800">{data.hostname}</dd>
                <dt className="text-zinc-500">Uptime</dt>
                <dd className="text-zinc-800">{fmtUptime(data.uptime_seconds)}</dd>
                <dt className="text-zinc-500">Platform</dt>
                <dd className="text-xs text-zinc-800">{data.platform}</dd>
                <dt className="text-zinc-500">Collected</dt>
                <dd className="text-xs text-zinc-800">
                  {new Date(data.collected_at).toLocaleString()}
                </dd>
              </dl>
            </Card>

            <Card className="lg:col-span-2">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                CPU
              </h2>
              <UsageBar percent={data.cpu.percent} />
              <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div>
                  <dt className="text-zinc-500">Usage</dt>
                  <dd className="text-zinc-800">{fmtPercent(data.cpu.percent)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Cores</dt>
                  <dd className="text-zinc-800">{data.cpu.count}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Load (1m)</dt>
                  <dd className="text-zinc-800">
                    {data.cpu.load_avg_1m != null ? data.cpu.load_avg_1m.toFixed(2) : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Load (5m / 15m)</dt>
                  <dd className="text-zinc-800">
                    {data.cpu.load_avg_5m != null ? data.cpu.load_avg_5m.toFixed(2) : '—'}
                    {' / '}
                    {data.cpu.load_avg_15m != null ? data.cpu.load_avg_15m.toFixed(2) : '—'}
                  </dd>
                </div>
              </dl>
            </Card>
          </section>

          <section className="mb-4 grid gap-4 md:grid-cols-2">
            <MemoryCard title="Memory" memory={data.memory} />
            {data.swap ? <MemoryCard title="Swap" memory={data.swap} /> : null}
          </section>

          <section className="mb-4">
            <Card>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Disk
              </h2>
              <div className="grid gap-3 md:grid-cols-2">
                {data.disks.map((disk) => (
                  <DiskCard key={`${disk.path}:${disk.mountpoint}`} disk={disk} />
                ))}
              </div>
            </Card>
          </section>

          <section>
            <Card>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Database
              </h2>
              <p className="mb-3 text-sm text-zinc-600">
                Postgres size:{' '}
                <span className="font-medium text-zinc-800">{fmtBytes(data.database.size_bytes)}</span>
              </p>
              <div className="overflow-x-auto rounded-lg border border-zinc-200">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">Table</th>
                      <th className="px-3 py-2 font-medium text-right">Rows</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {data.database.table_counts.map((row) => (
                      <tr key={row.table}>
                        <td className="px-3 py-2 font-mono text-xs text-zinc-800">{row.table}</td>
                        <td className="px-3 py-2 text-right text-zinc-800">
                          {row.count.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>
        </>
      ) : null}
    </>
  )
}
