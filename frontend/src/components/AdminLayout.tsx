import { Link, Outlet, useLocation } from 'react-router-dom'

import { AppNavBar, type NavItem } from './AppNavBar'
import { DashboardSwitchLink } from './DashboardSwitchLink'
import { UserAccountMenu } from './UserAccountMenu'
import { PageShell } from './ui'
import { useMe } from '../lib/auth'

function isBolhaPath(pathname: string) {
  return pathname === '/admin/bolha' || pathname.startsWith('/admin/bolha/')
}

const ADMIN_NAV: NavItem[] = [
  { type: 'link', to: '/admin', label: 'Home', end: true },
  { type: 'link', to: '/admin/users', label: 'Users' },
  { type: 'link', to: '/admin/listings', label: 'Listings' },
  {
    type: 'group',
    label: 'Bolha',
    isActive: isBolhaPath,
    children: [
      {
        to: '/admin/bolha',
        label: 'Control panel',
        isActive: (pathname) => pathname === '/admin/bolha',
      },
      {
        to: '/admin/bolha/http-logs',
        label: 'Logs',
        isActive: (pathname) => pathname === '/admin/bolha/http-logs',
      },
      {
        to: '/admin/bolha/listings',
        label: 'Listings',
        isActive: (pathname) => pathname === '/admin/bolha/listings',
      },
    ],
  },
  {
    type: 'group',
    label: 'Avtonet',
    isActive: (pathname) =>
      pathname === '/admin/avtonet' || pathname.startsWith('/admin/avtonet/'),
    children: [
      {
        to: '/admin/avtonet',
        label: 'Control panel',
        isActive: (pathname) => pathname === '/admin/avtonet',
      },
      {
        to: '/admin/avtonet/http-logs',
        label: 'Logs',
        isActive: (pathname) => pathname === '/admin/avtonet/http-logs',
      },
      {
        to: '/admin/avtonet/listings',
        label: 'Listings',
        isActive: (pathname) => pathname === '/admin/avtonet/listings',
      },
    ],
  },
]

export function AdminLayout() {
  const location = useLocation()
  const me = useMe()

  const isAdmin = Boolean(me.data?.is_admin)
  const displayName = me.data?.display_name || me.data?.email || 'Account'

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 text-zinc-500">
        Loading…
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <PageShell>
        <h1 className="text-lg font-semibold">Admins only</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Your account doesn't have admin access.{' '}
          <Link to="/dash" className="text-indigo-600 hover:underline">
            Back to home
          </Link>
        </p>
      </PageShell>
    )
  }

  return (
    <PageShell wide>
      <AppNavBar
        key={location.pathname}
        logoTo="/admin"
        logoVariant="admin"
        items={ADMIN_NAV}
        trailing={({ onNavigate, layout }) => (
          <UserAccountMenu displayName={displayName} onClose={onNavigate} layout={layout}>
            <DashboardSwitchLink to="/dash" target="user" onClick={onNavigate} />
          </UserAccountMenu>
        )}
      />

      <Outlet />
    </PageShell>
  )
}
