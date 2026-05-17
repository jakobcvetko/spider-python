import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

import { AppLogo } from './AppLogo'
import type { UserAccountMenuLayout } from './UserAccountMenu'

const NAV_LINK =
  'rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-zinc-100'

function navLinkClass(isActive: boolean) {
  return `${NAV_LINK} ${isActive ? 'bg-zinc-100 text-zinc-900' : 'text-zinc-600'}`
}

const MOBILE_NAV_LINK = `${NAV_LINK} text-base py-3`

function mobileNavLinkClass(isActive: boolean) {
  return `${MOBILE_NAV_LINK} ${isActive ? 'bg-zinc-100 text-zinc-900' : 'text-zinc-700'}`
}

export type NavLinkItem = {
  type: 'link'
  to: string
  label: string
  end?: boolean
}

export type NavGroupItem = {
  type: 'group'
  label: string
  isActive: (pathname: string) => boolean
  children: {
    to: string
    label: string
    isActive: (pathname: string) => boolean
  }[]
}

export type NavItem = NavLinkItem | NavGroupItem

export type NavTrailingContext = {
  onNavigate: () => void
  layout: UserAccountMenuLayout
}

export type NavTrailing = (ctx: NavTrailingContext) => ReactNode

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-4 w-4 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
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
  )
}

function NavGroupDesktop({
  item,
  onNavigate,
}: {
  item: NavGroupItem
  onNavigate: () => void
}) {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const active = item.isActive(location.pathname)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  const childClass = (isChildActive: (pathname: string) => boolean) => {
    const childActive = isChildActive(location.pathname)
    return `block px-4 py-2 text-sm ${
      childActive
        ? 'bg-zinc-100 font-medium text-zinc-900'
        : 'text-zinc-700 hover:bg-zinc-100'
    }`
  }

  return (
    <div className="relative hidden md:block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1 ${navLinkClass(active)}`}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        {item.label}
        <Chevron open={open} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 z-20 mt-1 min-w-[10.5rem] rounded-lg border border-zinc-200 bg-white py-1 shadow-lg"
        >
          {item.children.map((child) => (
            <NavLink
              key={child.to}
              to={child.to}
              role="menuitem"
              className={childClass(child.isActive)}
              onClick={() => {
                setOpen(false)
                onNavigate()
              }}
            >
              {child.label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

function NavGroupMobile({
  item,
  onNavigate,
}: {
  item: NavGroupItem
  onNavigate: () => void
}) {
  const location = useLocation()
  const [expanded, setExpanded] = useState(item.isActive(location.pathname))
  const active = item.isActive(location.pathname)

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className={`flex w-full items-center justify-between ${mobileNavLinkClass(active)}`}
        aria-expanded={expanded}
      >
        {item.label}
        <Chevron open={expanded} />
      </button>
      {expanded && (
        <div className="ml-3 mt-1 flex flex-col gap-0.5 border-l-2 border-zinc-200 pl-3">
          {item.children.map((child) => (
            <NavLink
              key={child.to}
              to={child.to}
              onClick={onNavigate}
              className={({ isActive: linkActive }) =>
                mobileNavLinkClass(child.isActive(location.pathname) || linkActive)
              }
            >
              {child.label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

export function AppNavBar({
  logoTo,
  logoVariant,
  items,
  trailing,
  onNavigate,
}: {
  logoTo: string
  logoVariant?: 'admin'
  items: NavItem[]
  trailing: NavTrailing
  onNavigate?: () => void
}) {
  const [mobileOpen, setMobileOpen] = useState(false)

  const closeMobile = () => {
    setMobileOpen(false)
    onNavigate?.()
  }

  useEffect(() => {
    if (!mobileOpen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [mobileOpen])

  const closeMenus = () => onNavigate?.()

  return (
    <header className="mb-4 border-b border-zinc-200 pb-3">
      <div className="flex items-center justify-between gap-2">
        <AppLogo to={logoTo} variant={logoVariant} onClick={closeMenus} />

        <nav className="hidden items-center gap-0.5 md:flex" aria-label="Main">
          {items.map((item) =>
            item.type === 'link' ? (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={closeMenus}
                className={({ isActive }) => navLinkClass(isActive)}
              >
                {item.label}
              </NavLink>
            ) : (
              <NavGroupDesktop key={item.label} item={item} onNavigate={closeMenus} />
            ),
          )}
        </nav>

        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            className="rounded-lg p-2 text-zinc-600 hover:bg-zinc-100 md:hidden"
            aria-expanded={mobileOpen}
            aria-controls="app-mobile-nav"
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? (
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
              </svg>
            ) : (
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path
                  fillRule="evenodd"
                  d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zm0 5A.75.75 0 012.75 9h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 9.75zm0 5a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75z"
                  clipRule="evenodd"
                />
              </svg>
            )}
          </button>
          <div className="hidden md:block">
            {trailing({ onNavigate: closeMenus, layout: 'dropdown' })}
          </div>
        </div>
      </div>

      {mobileOpen && (
        <div
          id="app-mobile-nav"
          className="fixed inset-0 z-50 flex flex-col bg-white md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
            <AppLogo to={logoTo} variant={logoVariant} onClick={closeMobile} />
            <button
              type="button"
              className="rounded-lg p-2 text-zinc-600 hover:bg-zinc-100"
              aria-label="Close menu"
              onClick={closeMobile}
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
              </svg>
            </button>
          </div>

          <nav className="flex-1 overflow-y-auto px-4 py-4" aria-label="Main">
            <div className="flex flex-col gap-1">
              {items.map((item) =>
                item.type === 'link' ? (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={closeMobile}
                    className={({ isActive }) => mobileNavLinkClass(isActive)}
                  >
                    {item.label}
                  </NavLink>
                ) : (
                  <NavGroupMobile key={item.label} item={item} onNavigate={closeMobile} />
                ),
              )}
            </div>
          </nav>

          <div className="border-t border-zinc-200 px-4 py-4">
            {trailing({ onNavigate: closeMobile, layout: 'stacked' })}
          </div>
        </div>
      )}
    </header>
  )
}
