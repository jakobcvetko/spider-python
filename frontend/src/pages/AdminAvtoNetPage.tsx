import { AdminSourceDebugScrape } from '../components/AdminSourceDebugScrape'

export default function AdminAvtoNetPage() {
  return (
    <AdminSourceDebugScrape sourceName="avto.net" title="avto.net debug">
      <p>
        The worker requests the default search URL built in{' '}
        <code className="text-zinc-800">scraper/sources/avto_net.py</code> (wide-open filters,
        first page). avto.net is commonly protected by a Cloudflare-style edge; automated clients
        often get <strong className="text-zinc-800">403</strong> with no usable HTML.
      </p>
      <p>
        On a successful 200 HTML response, the parser extracts listing cards into{' '}
        <code className="text-zinc-800">ScrapedItem</code> rows and the worker upserts into Postgres
        (deduped by source + external id).
      </p>
      <p className="text-amber-700/90">
        Expect <code className="text-amber-800">403</code> until the fetch path is upgraded (e.g.
        browser automation or carefully tuned headers) — this page is for watching exactly what the
        worker sees on the wire.
      </p>
    </AdminSourceDebugScrape>
  )
}
