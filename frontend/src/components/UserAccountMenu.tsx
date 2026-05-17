import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { useLogout } from '../lib/auth'

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-4 w-4 shrink-0 text-zinc-500 transition-transform ${open ? 'rotate-180' : ''}`}
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

export type UserAccountMenuLayout = 'dropdown' | 'stacked'

export function UserAccountMenu({
  displayName,
  onClose,
  children,
  layout = 'dropdown',
}: {
  displayName: string
  onClose?: () => void
  children?: ReactNode
  layout?: UserAccountMenuLayout
}) {
  const logout = useLogout()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const close = () => {
    setOpen(false)
    onClose?.()
  }

  useEffect(() => {
    if (layout !== 'dropdown' || !open) return
    const onPointerDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open, layout])

  const onLogout = async () => {
    close()
    await logout.mutateAsync()
    navigate('/', { replace: true })
  }

  if (layout === 'stacked') {
    return (
      <div className="space-y-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">Account</p>
          <p className="mt-0.5 truncate text-sm font-medium text-zinc-900">{displayName}</p>
        </div>
        {children ? <div className="space-y-0.5">{children}</div> : null}
        <button
          type="button"
          disabled={logout.isPending}
          onClick={onLogout}
          className="w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50"
        >
          {logout.isPending ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    )
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex max-w-[min(12rem,40vw)] items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-100 sm:max-w-[14rem] sm:px-3"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span className="truncate">{displayName}</span>
        <Chevron open={open} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-1 min-w-[8.5rem] rounded-lg border border-zinc-200 bg-white py-1 shadow-lg"
        >
          {children ? (
            <div className="border-b border-zinc-100" onClick={close}>
              {children}
            </div>
          ) : null}
          <button
            type="button"
            role="menuitem"
            disabled={logout.isPending}
            onClick={onLogout}
            className="block w-full px-4 py-2 text-left text-sm text-zinc-700 hover:bg-zinc-100 disabled:opacity-50"
          >
            {logout.isPending ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      )}
    </div>
  )
}
