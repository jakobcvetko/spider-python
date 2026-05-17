import { Link } from 'react-router-dom'

import { TelegramConnection } from './TelegramConnection'
import { Button, Card } from './ui'
import { useTelegramStatus } from '../lib/telegram'

function StepMarker({
  step,
  done,
  active,
}: {
  step: number
  done: boolean
  active: boolean
}) {
  if (done) {
    return (
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path
            fillRule="evenodd"
            d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    )
  }
  return (
    <span
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
        active ? 'bg-indigo-600 text-white' : 'bg-zinc-200 text-zinc-500'
      }`}
    >
      {step}
    </span>
  )
}

export function HomeOnboarding({
  enabled,
  activeScraperCount,
}: {
  enabled: boolean
  activeScraperCount: number
}) {
  const telegram = useTelegramStatus(enabled)
  const connected = telegram.data?.connected ?? false
  const setupComplete = connected && activeScraperCount > 0

  if (setupComplete) return null

  const step1Done = connected
  const step2Active = step1Done && activeScraperCount === 0

  return (
    <Card>
      <div className="mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Get started
        </h2>
        <p className="mt-1 text-sm text-zinc-500">
          Connect Telegram, then create a scraper to start receiving match alerts.
        </p>
      </div>

      <ol className="space-y-4">
        <li className="flex gap-3">
          <StepMarker step={1} done={step1Done} active={!step1Done} />
          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <p className="font-medium text-zinc-900">Connect Telegram</p>
              <p className="text-sm text-zinc-500">
                Required for push alerts when new listings match your filters.
              </p>
            </div>

            {!step1Done && (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-3"
              >
                <p className="text-sm font-medium text-red-900">Telegram not connected</p>
                <p className="mt-1 text-sm text-red-800/90">
                  Connect your account to receive notifications — you will not get alerts
                  until this step is done.
                </p>
                <div className="mt-3 [&_ul]:mt-0">
                  <TelegramConnection />
                </div>
              </div>
            )}

            {step1Done && (
              <p className="text-sm text-emerald-700">
                Connected
                {telegram.data?.username ? ` as @${telegram.data.username}` : ''}.
              </p>
            )}
          </div>
        </li>

        <li className="flex gap-3">
          <StepMarker step={2} done={activeScraperCount > 0} active={step2Active} />
          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <p className="font-medium text-zinc-900">Create a scraper</p>
              <p className="text-sm text-zinc-500">
                Define what you are looking for on Bolha or Avto.net.
              </p>
            </div>

            {step2Active && (
              <div
                role="status"
                className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
              >
                <p className="text-sm font-medium text-amber-900">No active scrapers yet</p>
                <p className="mt-1 text-sm text-amber-800/90">
                  Add at least one scraper with Bolha or Avto.net enabled to start matching
                  listings.
                </p>
                <Link to="/scrapers" className="mt-3 inline-block">
                  <Button type="button" variant="primary" className="px-3 py-1.5">
                    Create scraper
                  </Button>
                </Link>
              </div>
            )}

            {!step1Done && (
              <p className="text-sm text-zinc-400">Complete step 1 first.</p>
            )}

            {activeScraperCount > 0 && (
              <p className="text-sm text-emerald-700">
                {activeScraperCount} active scraper{activeScraperCount === 1 ? '' : 's'}.
              </p>
            )}
          </div>
        </li>
      </ol>
    </Card>
  )
}
