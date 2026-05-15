import { AdminSourceDebugScrape } from '../components/AdminSourceDebugScrape'

export default function AdminBolhaPage() {
  return (
    <AdminSourceDebugScrape sourceName="bolha.com" title="bolha.com debug">
      <p>
        The worker requests{' '}
        <code className="rounded bg-zinc-800 px-1 py-0.5 text-zinc-200">
          https://www.bolha.com/avtomobili
        </code>{' '}
        (see <code className="text-zinc-200">SEARCH_URL</code> in{' '}
        <code className="text-zinc-200">scraper/sources/bolha.py</code>). Bolha often answers with a
        redirect to <code className="text-zinc-200">validate.perfdrive.com</code> (PerimeterX-style
        validation). Plain httpx cannot complete that challenge, so you may see 200 HTML that is
        not real listing markup.
      </p>
      <p>
        When the response is real search HTML, the parser collects links matching{' '}
        <code className="text-zinc-200">/oglas/</code> or car listing <code className="text-zinc-200">.html</code>{' '}
        URLs, walks up the DOM a few levels to guess price and location, and builds{' '}
        <code className="text-zinc-200">ScrapedItem</code> rows. Duplicates are skipped by external
        id parsed from the URL.
      </p>
      <p className="text-amber-200/90">
        If <code className="text-amber-100">parsed 0 candidate items</code> but HTTP shows 200, the
        HTML is probably a bot wall or the listing markup changed — use the request/response lines
        above to confirm where the browser ended up.
      </p>
    </AdminSourceDebugScrape>
  )
}
