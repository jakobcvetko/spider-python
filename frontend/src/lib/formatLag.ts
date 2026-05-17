/** Short lag between site publish time and when we stored the listing (created_at). */
export function formatDiscoveryLag(
  publishedAt: string | null | undefined,
  createdAt: string | null | undefined,
): string | null {
  if (!publishedAt || !createdAt) return null
  const pub = Date.parse(publishedAt)
  const created = Date.parse(createdAt)
  if (!Number.isFinite(pub) || !Number.isFinite(created)) return null
  const sec = Math.max(0, Math.round((created - pub) / 1000))
  if (sec < 60) return `${sec}sec`
  if (sec < 3600) return `${Math.round(sec / 60)}min`
  if (sec < 86_400) return `${Math.round(sec / 3600)}h`
  if (sec < 86_400 * 30) return `${Math.round(sec / 86_400)}d`
  return `${Math.round(sec / (86_400 * 30))}mo`
}

export function discoveryLagTitle(
  publishedAt: string | null | undefined,
  createdAt: string | null | undefined,
): string | undefined {
  if (!publishedAt || !createdAt) return undefined
  try {
    const pub = new Date(publishedAt).toLocaleString()
    const created = new Date(createdAt).toLocaleString()
    return `Published ${pub} · ingested ${created}`
  } catch {
    return undefined
  }
}
