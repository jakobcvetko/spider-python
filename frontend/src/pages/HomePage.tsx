import { Link } from 'react-router-dom'

import { DailyMatchesChart } from '../components/DailyMatchesChart'
import { Button, Card } from '../components/ui'
import { useMe } from '../lib/auth'
import { type Scraper, useScrapers } from '../lib/scrapers'
import { useDailyMatches } from '../lib/stats'

const MATCH_DAYS = 14

function formatSources(scraper: Scraper): string {
  const sources: string[] = []
  if (scraper.bolha_enabled) sources.push('Bolha')
  if (scraper.avtonet_enabled) sources.push('Avto.net')
  return sources.length > 0 ? sources.join(', ') : 'No sources'
}

function isActiveScraper(scraper: Scraper): boolean {
  return scraper.bolha_enabled || scraper.avtonet_enabled
}

export default function HomePage() {
  const me = useMe()
  const enabled = Boolean(me.data)
  const dailyMatches = useDailyMatches(enabled, MATCH_DAYS)
  const scrapers = useScrapers(enabled)

  const activeScrapers = (scrapers.data ?? []).filter(isActiveScraper)
  const chartDays = dailyMatches.data?.days ?? []
  const periodTotal = dailyMatches.data?.total ?? 0

  return (
    <>
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Home</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Your matches, scrapers, and notification connections at a glance.
        </p>
      </header>

      <div className="space-y-6">
        <Card>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Daily matches
              </h2>
              <p className="text-sm text-zinc-500">
                Last {MATCH_DAYS} days — listings that matched your scrapers.
              </p>
            </div>
            {dailyMatches.isFetching && !dailyMatches.isLoading && (
              <span className="text-xs text-zinc-500">Refreshing…</span>
            )}
            {!dailyMatches.isLoading && !dailyMatches.error && (
              <p className="text-sm text-zinc-700">
                <span className="font-semibold tabular-nums">{periodTotal}</span>{' '}
                in period
              </p>
            )}
          </div>

          {dailyMatches.isLoading ? (
            <p className="text-sm text-zinc-500">Loading chart…</p>
          ) : dailyMatches.error ? (
            <p className="text-sm text-red-600">Failed to load match stats.</p>
          ) : chartDays.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No match data yet. Create a scraper and run the Bolha worker and matcher.
            </p>
          ) : (
            <DailyMatchesChart days={chartDays} />
          )}
        </Card>

        <Card>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Active scrapers
              </h2>
              <p className="text-sm text-zinc-500">
                Scrapers currently watching at least one source.
              </p>
            </div>
            <Link to="/scrapers">
              <Button type="button" variant="ghost" className="px-3 py-1.5">
                Manage scrapers
              </Button>
            </Link>
          </div>

          {scrapers.isLoading ? (
            <p className="text-sm text-zinc-500">Loading scrapers…</p>
          ) : scrapers.error ? (
            <p className="text-sm text-red-600">Failed to load scrapers.</p>
          ) : activeScrapers.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No active scrapers.{' '}
              <Link to="/scrapers" className="font-medium text-indigo-600 hover:underline">
                Create one
              </Link>{' '}
              to start matching listings.
            </p>
          ) : (
            <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200">
              {activeScrapers.map((scraper) => (
                <li
                  key={scraper.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-zinc-900">{scraper.name}</p>
                    <p className="text-sm text-zinc-500">{formatSources(scraper)}</p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden />
                    Active
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Connections
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Receive realtime notifications when new listings match your scrapers.
          </p>

          <ul className="mt-4 space-y-3">
            <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-zinc-50/80 px-4 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-100 text-sky-700"
                  aria-hidden
                >
                  <TelegramIcon />
                </span>
                <div>
                  <p className="font-medium text-zinc-900">Telegram</p>
                  <p className="text-sm text-zinc-500">
                    Push alerts for new matches as they are found.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                  In progress
                </span>
                <Button type="button" variant="ghost" disabled className="px-3 py-1.5">
                  Connect
                </Button>
              </div>
            </li>
          </ul>
        </Card>
      </div>
    </>
  )
}

function TelegramIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  )
}
