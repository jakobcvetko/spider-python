import { Link } from 'react-router-dom'

import { DailyMatchesChart } from '../components/DailyMatchesChart'
import { TelegramConnection } from '../components/TelegramConnection'
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
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Home</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Your matches, scrapers, and notification connections at a glance.
        </p>
      </header>

      <div className="space-y-5">
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
            <ul className="divide-y divide-zinc-200 border-y border-zinc-200 -mx-3 sm:mx-0">
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

          <TelegramConnection />
        </Card>
      </div>
    </>
  )
}
