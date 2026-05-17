import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useMarketingLocale } from '../hooks/useMarketingLocale'
import { MarketingFooter } from './MarketingFooter'

type AuthPageShellProps = {
  title: string
  description: string
  children: ReactNode
}

export function AuthPageShell({ title, description, children }: AuthPageShellProps) {
  const { t } = useMarketingLocale()

  return (
    <div className="landing-page flex min-h-svh flex-col bg-zinc-950 text-zinc-100">
      <header className="flex items-center justify-between px-5 py-4 sm:px-8">
        <Link to="/" className="flex items-baseline gap-2">
          <span className="font-display text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            Spider
          </span>
        </Link>
        <Link
          to="/"
          className="text-sm font-medium text-zinc-400 transition hover:text-white"
        >
          {t.back}
        </Link>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center px-5 pt-4 pb-4 sm:px-8">
        <div className="w-full max-w-md">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-white">
            {title}
          </h1>
          <p className="mt-2 text-sm text-zinc-400">{description}</p>
          <div className="mt-8 rounded-2xl border border-white/10 bg-zinc-900/80 p-6 sm:p-7">
            {children}
          </div>
        </div>
      </main>

      <MarketingFooter />
    </div>
  )
}
