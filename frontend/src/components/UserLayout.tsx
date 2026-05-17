import { Outlet, useLocation } from 'react-router-dom'

import { AppNavBar, type NavItem } from './AppNavBar'
import { DashboardSwitchLink } from './DashboardSwitchLink'
import { UserAccountMenu } from './UserAccountMenu'
import { PageShell } from './ui'
import { useMe } from '../lib/auth'

const USER_NAV: NavItem[] = [
  { type: 'link', to: '/dash', label: 'Setup', end: true },
  { type: 'link', to: '/dash/scrapers', label: 'Scrapers' },
  { type: 'link', to: '/dash/listings', label: 'Listings' },
]

export function UserLayout() {
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

  return (
    <PageShell>
      <AppNavBar
        key={location.pathname}
        logoTo="/"
        items={USER_NAV}
        trailing={({ onNavigate, layout }) => (
          <UserAccountMenu displayName={displayName} onClose={onNavigate} layout={layout}>
            {isAdmin && (
              <DashboardSwitchLink to="/admin" target="admin" onClick={onNavigate} />
            )}
          </UserAccountMenu>
        )}
      />

      <Outlet />
    </PageShell>
  )
}
