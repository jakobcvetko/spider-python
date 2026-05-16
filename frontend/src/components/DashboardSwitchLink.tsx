import { Link } from 'react-router-dom'

const MENU_ITEM =
  'flex w-full items-center gap-2 px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100'

function ArrowRightOnRectangleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z"
        clipRule="evenodd"
      />
      <path
        fillRule="evenodd"
        d="M19 10a.75.75 0 00-.75-.75H8.704l1.048-.943a.75.75 0 10-1.004-1.114l-2.5 2.25a.75.75 0 000 1.114l2.5 2.25a.75.75 0 101.004-1.114l-1.048-.943h9.546A.75.75 0 0019 10z"
        clipRule="evenodd"
      />
    </svg>
  )
}

function ArrowLeftOnRectangleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z"
        clipRule="evenodd"
      />
      <path
        fillRule="evenodd"
        d="M6.75 10a.75.75 0 01.75-.75h9.69l-1.22-1.22a.75.75 0 111.06-1.06l2.5 2.5a.75.75 0 010 1.06l-2.5 2.5a.75.75 0 11-1.06-1.06l1.22-1.22H7.5a.75.75 0 01-.75-.75z"
        clipRule="evenodd"
      />
    </svg>
  )
}

type DashboardSwitchLinkProps = {
  to: string
  target: 'admin' | 'user'
  onClick?: () => void
}

export function DashboardSwitchLink({ to, target, onClick }: DashboardSwitchLinkProps) {
  const label = target === 'admin' ? 'Admin' : 'User'
  const title = target === 'admin' ? 'Admin dashboard' : 'User dashboard'
  const Icon = target === 'admin' ? ArrowRightOnRectangleIcon : ArrowLeftOnRectangleIcon

  return (
    <Link
      to={to}
      role="menuitem"
      onClick={onClick}
      className={MENU_ITEM}
      aria-label={title}
      title={title}
    >
      <Icon className="h-4 w-4 shrink-0 text-zinc-500" />
      <span className="font-medium">{label}</span>
      <span className="sr-only"> dashboard</span>
    </Link>
  )
}
