import { Link } from 'react-router-dom'

import { DailyMatchesChart } from '../components/DailyMatchesChart'
import { HomeOnboarding } from '../components/HomeOnboarding'
import { countActiveScrapers } from '../lib/scrapers'
import { Button, Card } from '../components/ui'
import { useMe } from '../lib/auth'
import { useScrapers } from '../lib/scrapers'
import { useDailyMatches } from '../lib/stats'

const MATCH_DAYS = 14

export default function HomePage() {
  const me = useMe()
  const enabled = Boolean(me.data)
  const dailyMatches = useDailyMatches(enabled, MATCH_DAYS)
  const scrapers = useScrapers(enabled)

  const activeScraperCount = countActiveScrapers(scrapers.data)
  const chartDays = dailyMatches.data?.days ?? []
  const periodTotal = dailyMatches.data?.total ?? 0

  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Home</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Your matches and setup progress at a glance.
        </p>
      </header>

      <div className="space-y-5">
        <HomeOnboarding enabled={enabled} activeScraperCount={activeScraperCount} />

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
              No match data yet. Complete setup above, then run the Bolha worker and matcher.
            </p>
          ) : (
            <DailyMatchesChart days={chartDays} />
          )}
        </Card>

        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Scrapers
              </h2>
              {scrapers.isLoading ? (
                <p className="mt-1 text-sm text-zinc-500">Loading…</p>
              ) : scrapers.error ? (
                <p className="mt-1 text-sm text-red-600">Failed to load scrapers.</p>
              ) : (
                <p className="mt-1 text-sm text-zinc-700">
                  <span className="text-2xl font-semibold tabular-nums text-zinc-900">
                    {activeScraperCount}
                  </span>{' '}
                  active scraper{activeScraperCount === 1 ? '' : 's'}
                </p>
              )}
            </div>
            <Link to="/dash/scrapers">
              <Button type="button" variant="ghost" className="px-3 py-1.5">
                Manage scrapers
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    </>
  )
}
