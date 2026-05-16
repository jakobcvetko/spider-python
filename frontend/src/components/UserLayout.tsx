import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { AppLogo } from './AppLogo'
import { DashboardSwitchLink } from './DashboardSwitchLink'
import { PageShell } from './ui'
import { useLogout, useMe } from '../lib/auth'

const NAV_LINK =
  'rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-zinc-100'

function navLinkClass(isActive: boolean) {
  return `${NAV_LINK} ${isActive ? 'bg-zinc-100 text-zinc-900' : 'text-zinc-600'}`
}

export function UserLayout() {
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  const isAdmin = Boolean(me.data?.is_admin)
  const displayName = me.data?.display_name || me.data?.email || 'Account'

  const closeUserMenu = () => setUserMenuOpen(false)

  useEffect(() => {
    if (!userMenuOpen) return
    const onPointerDown = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [userMenuOpen])

  const onLogout = async () => {
    setUserMenuOpen(false)
    await logout.mutateAsync()
    navigate('/login', { replace: true })
  }

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 text-zinc-500">
        Loading…
      </div>
    )
  }

  return (
    <PageShell>
      <nav className="mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-zinc-200 pb-4">
        <div className="flex flex-wrap items-center gap-1">
          <AppLogo to="/" onClick={closeUserMenu} />
          <span className="mx-1 hidden h-5 w-px bg-zinc-200 sm:block" aria-hidden />
          <NavLink
            to="/"
            end
            onClick={closeUserMenu}
            className={({ isActive }) => navLinkClass(isActive)}
          >
            Home
          </NavLink>
          <NavLink
            to="/scrapers"
            onClick={closeUserMenu}
            className={({ isActive }) => navLinkClass(isActive)}
          >
            Scrapers
          </NavLink>
          <NavLink
            to="/listings"
            onClick={closeUserMenu}
            className={({ isActive }) => navLinkClass(isActive)}
          >
            Listings
          </NavLink>
        </div>

        <div className="relative" ref={userMenuRef}>
          <button
            type="button"
            onClick={() => setUserMenuOpen((open) => !open)}
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-100"
            aria-expanded={userMenuOpen}
            aria-haspopup="menu"
          >
            <span className="max-w-48 truncate">{displayName}</span>
            <svg
              className={`h-4 w-4 shrink-0 text-zinc-500 transition-transform ${userMenuOpen ? 'rotate-180' : ''}`}
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden
            >
              <path
                fillRule="evenodd"
                d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          {userMenuOpen && (
            <div
              role="menu"
              className="absolute right-0 z-20 mt-1 min-w-[8.5rem] rounded-lg border border-zinc-200 bg-white py-1 shadow-lg"
            >
              {isAdmin && (
                <DashboardSwitchLink
                  to="/admin"
                  target="admin"
                  onClick={closeUserMenu}
                />
              )}
              <button
                type="button"
                role="menuitem"
                disabled={logout.isPending}
                onClick={onLogout}
                className="block w-full px-4 py-2 text-left text-sm text-zinc-800 hover:bg-zinc-100 disabled:opacity-50"
              >
                {logout.isPending ? 'Signing out…' : 'Sign out'}
              </button>
            </div>
          )}
        </div>
      </nav>

      <Outlet />
    </PageShell>
  )
}
