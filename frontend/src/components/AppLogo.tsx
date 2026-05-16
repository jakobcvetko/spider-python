import { Link } from 'react-router-dom'

type AppLogoProps = {
  to: string
  variant?: 'user' | 'admin'
  onClick?: () => void
}

export function AppLogo({ to, variant = 'user', onClick }: AppLogoProps) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="mr-2 flex shrink-0 items-center rounded-lg py-2 pr-2 pl-1 text-zinc-900 hover:bg-zinc-100"
    >
      <span className="text-lg font-semibold tracking-tight">
        Spider
        {variant === 'admin' && (
          <sup className="ml-0.5 text-[0.55rem] font-medium uppercase tracking-widest text-indigo-600">
            Admin
          </sup>
        )}
      </span>
    </Link>
  )
}
