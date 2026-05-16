import { Link } from 'react-router-dom'

import { AdminSourceDebugScrape } from '../components/AdminSourceDebugScrape'
import { BolhaProgressiveDashboard } from '../components/BolhaProgressiveDashboard'

export default function AdminBolhaPage() {
  return (
    <AdminSourceDebugScrape
      sourceName="bolha.com"
      title="bolha.com debug"
      prependSlot={({ live }) => (
        <>
          <BolhaProgressiveDashboard enabled={true} liveEvents={live.events} />
          <p className="mb-4 text-sm text-zinc-400">
            <Link to="/admin/bolha/ads" className="text-indigo-300 hover:underline">
              bolha_ads registry
            </Link>
            {' '}
            (every probed ID + scrape history) ·{' '}
            <Link to="/admin/bolha/ad-states" className="text-indigo-300 hover:underline">
              bolha_ad_states
            </Link>
            {' '}
            (pipeline queue)
          </p>
        </>
      )}
    >
      <p>
        Bolha uses <strong className="text-zinc-200">progressive-scrape</strong> on{' '}
        <code className="rounded bg-zinc-800 px-1 py-0.5 text-zinc-200">iapi.bolha.com</code>: ad
        URLs use monotonic integer IDs. Example pattern:{' '}
        <code className="text-zinc-200">
          https://iapi.bolha.com/&lt;category&gt;/&lt;slug&gt;-oglas-&lt;id&gt;
        </code>
        — the numeric <code className="text-zinc-200">&lt;id&gt;</code> is what matters; the worker
        probes with a fixed template URL so every ID is reachable without knowing the real slug.
      </p>
      <p>
        The worker runs two sources: <code className="text-zinc-200">bolha.lookahead</code> loops
        forever, probing <code className="text-zinc-200">LOOKAHEAD_ADS</code> IDs above{' '}
        <code className="text-zinc-200">max(homepage_max, db_max, last_working)</code> each batch.
        After a batch with no active ad it sleeps{' '}
        <code className="text-zinc-200">LOOKAHEAD_TIMEOUT_SECONDS</code>. When it finds an active ad
        it promotes lower-ID lookahead rows to <code className="text-zinc-200">pending_fallback</code>{' '}
        (with <code className="text-zinc-200">first_fallback_scrape_at</code>), updates last-working,
        upserts the listing, and immediately starts the next batch. When it finds{' '}
        <code className="text-zinc-200">inactive</code> on a redirect (canonical listing URL) the slot
        is <code className="text-zinc-200">expired</code>: it updates last-working to that id, clears
        lower <code className="text-zinc-200">lookahead</code> rows without backfill, and starts the
        next batch; same-URL inactive ids are <code className="text-zinc-200">not_yet_created</code>{' '}
        and the scan continues in the window.{' '}
        <code className="text-zinc-200">bolha.backfill</code> works eligible IDs below{' '}
        <code className="text-zinc-200">last_working</code> from high to low with a{' '}
        <code className="text-zinc-200">FALLBACK_TIMEOUT_SECONDS</code> window from first failed check.{' '}
        <code className="text-zinc-200">bolha.scout</code> (<code className="text-zinc-200">make bolha:scout</code>)
        is a one-shot worker: it gallops (+1000, doubling) and binary-searches progressive-scrape
        probes to find the highest known ID (active or expired), updates{' '}
        <code className="text-zinc-200">last_working_ad_id</code>, and exits — use when the anchor
        is far behind a large block of <code className="text-zinc-200">not_yet_created</code> IDs.
      </p>
      <p>
        Constants live in <code className="text-zinc-200">scraper/sources/bolha_common.py</code>. The
        cycle panel reads <code className="text-zinc-200">bolha_scrape_meta</code>,{' '}
        <code className="text-zinc-200">bolha_ad_probes</code>, and{' '}
        <code className="text-zinc-200">bolha_ad_states</code> (poll + WebSocket{' '}
        <code className="text-zinc-200">bolha_progressive_tick</code> invalidation). Listings still use{' '}
        <code className="text-zinc-200">source = bolha.com</code>.
      </p>
      <p className="text-amber-200/90">
        If nothing new appears for a long time, the homepage max may lag behind real publishes, or
        you may be in a block of draft IDs: check the debug log for HTTP status and{' '}
        <code className="text-amber-100">adStatus</code> from the GTM bootstrap block.
      </p>
    </AdminSourceDebugScrape>
  )
}
