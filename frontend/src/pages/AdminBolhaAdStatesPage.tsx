import { Link, useNavigate } from 'react-router-dom'

import { BolhaAdStatesTable } from '../components/BolhaAdStatesTable'
import { Button, Card, PageShell } from '../components/ui'
import { useLogout, useMe } from '../lib/auth'

export default function AdminBolhaAdStatesPage() {
  const navigate = useNavigate()
  const me = useMe()
  const logout = useLogout()
  const isAdmin = Boolean(me.data?.is_admin)

  const onLogout = async () => {
    await logout.mutateAsync()
    navigate('/login', { replace: true })
  }

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-400">
        Loading…
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <PageShell>
        <Card>
          <h1 className="mb-2 text-lg font-semibold">Admins only</h1>
          <p className="text-sm text-zinc-400">
            Your account doesn't have admin access.{' '}
            <Link to="/" className="text-indigo-300 hover:underline">
              Back to listings
            </Link>
          </p>
        </Card>
      </PageShell>
    )
  }

  return (
    <PageShell>
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
            <Link to="/admin" className="text-indigo-300 hover:underline">
              Admin
            </Link>
            <span className="text-zinc-600"> / </span>
            <Link to="/admin/bolha" className="text-indigo-300 hover:underline">
              bolha.com debug
            </Link>
            <span className="text-zinc-600"> / </span>
            <span className="text-zinc-400">ad states</span>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">bolha_ad_states</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Signed in as{' '}
            <span className="text-zinc-200">{me.data?.display_name || me.data?.email}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/admin/bolha"
            className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800"
          >
            Bolha debug
          </Link>
          <Link
            to="/admin"
            className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800"
          >
            Admin home
          </Link>
          <Link
            to="/"
            className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-800"
          >
            Listings
          </Link>
          <Button variant="ghost" loading={logout.isPending} onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </header>

      <p className="mb-4 text-sm text-zinc-400">
        Progressive scrape state per ad ID. This list polls the API every few seconds.
      </p>

      <BolhaAdStatesTable enabled={true} />
    </PageShell>
  )
}
