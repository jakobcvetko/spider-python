import { TelegramConnection } from '../components/TelegramConnection'
import { SetupGuide } from '../components/SetupGuide'
import { Card } from '../components/ui'
import { useMe } from '../lib/auth'
import { countActiveScrapers, useScrapers } from '../lib/scrapers'
import { useTelegramStatus } from '../lib/telegram'

export default function HomePage() {
  const me = useMe()
  const enabled = Boolean(me.data)
  const telegram = useTelegramStatus(enabled)
  const scrapers = useScrapers(enabled)

  const telegramConnected = telegram.data?.connected ?? false
  const activeScraperCount = countActiveScrapers(scrapers.data)

  return (
    <>
      <header className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Setup</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Connect Telegram and create scrapers to receive match alerts.
        </p>
      </header>

      <div className="space-y-5">
        <Card>
          <div className="mb-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
              Telegram
            </h2>
            <p className="mt-1 text-sm text-zinc-500">
              Push alerts when new listings match your scrapers. You can disconnect and
              reconnect anytime.
            </p>
          </div>
          <TelegramConnection />
        </Card>

        <SetupGuide
          telegramConnected={telegramConnected}
          activeScraperCount={activeScraperCount}
        />
      </div>
    </>
  )
}
