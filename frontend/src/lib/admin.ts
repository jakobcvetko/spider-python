import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { api } from "./api";

export type AdminUser = {
  id: string;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
};

export type ScraperEvent = {
  id: string;
  ts: number;
  kind: string;
  source: string | null;
  message: string | null;
  data: Record<string, unknown>;
};

export type ScraperStatus = {
  connected: boolean;
  last_heartbeat_ts: number | null;
  seconds_since_heartbeat: number | null;
  sources: string[];
  interval_seconds: number;
  recent_events: ScraperEvent[];
};

export type RunSourceResponse = {
  queued: boolean;
  reason: string;
  source: string;
};

export type BolhaAdMatchResponse = {
  ad_id: number;
  listing_id: string;
  matches_created: number;
};

export type AdminListing = {
  id: string;
  source: string;
  external_id: string;
  url: string;
  title: string;
  price_cents: number | null;
  currency: string | null;
  location: string | null;
  image_url: string | null;
  year: number | null;
  mileage_km: number | null;
  created_at: string;
  updated_at: string;
};

export const adminKeys = {
  users: ["admin", "users"] as const,
  scraperStatus: ["admin", "scraper", "status"] as const,
  listingsRoot: ["admin", "listings"] as const,
  bolhaProgressive: ["admin", "bolha", "progressive"] as const,
  bolhaAdStates: ["admin", "bolha", "ad-states"] as const,
  bolhaAds: ["admin", "bolha", "ads"] as const,
  avtonetAds: ["admin", "avtonet", "ads"] as const,
  avtonetState: ["admin", "avtonet", "state"] as const,
  avtonetProgressive: ["admin", "avtonet", "progressive"] as const,
  avtonetAdStates: ["admin", "avtonet", "ad-states"] as const,
};

/** Highest ad_id rows shown on the live bolha_ads registry table. */
export const BOLHA_ADS_TOP_LIMIT = 200;

/** Bolha HTTP log table on /admin/bolha/http-logs. */
export const BOLHA_HTTP_LOGS_LIMIT = 100;

const BOLHA_HTTP_KINDS = new Set(["http_request", "http_response"]);

export function isBolhaHttpEvent(ev: ScraperEvent): boolean {
  if (!BOLHA_HTTP_KINDS.has(ev.kind)) return false;
  const src = ev.source ?? "";
  return src.startsWith("bolha.");
}

/** Chronological Bolha HTTP request/response rows (capped, oldest first). */
export function useBolhaHttpLogs(events: ScraperEvent[]): ScraperEvent[] {
  return useMemo(() => {
    const filtered = events.filter(isBolhaHttpEvent);
    return filtered.slice(-BOLHA_HTTP_LOGS_LIMIT);
  }, [events]);
}

/** Matches backend ``LOOKAHEAD_ADS`` (bolha.lookahead window size). */
export const BOLHA_LOOKAHEAD_COUNT = 20;

/** Highest ad_id rows on the live avtonet_ads registry table. */
export const AVTONET_ADS_TOP_LIMIT = 200;

/** Avtonet HTTP log table on /admin/avtonet/http-logs. */
export const AVTONET_HTTP_LOGS_LIMIT = 100;

const AVTONET_HTTP_KINDS = new Set(["http_request", "http_response"]);

export function isAvtonetHttpEvent(ev: ScraperEvent): boolean {
  if (!AVTONET_HTTP_KINDS.has(ev.kind)) return false;
  const src = ev.source ?? "";
  return src === "avto.net" || src.startsWith("avto.net.");
}

export function useAvtonetHttpLogs(events: ScraperEvent[]): ScraperEvent[] {
  return useMemo(() => {
    const filtered = events.filter(isAvtonetHttpEvent);
    return filtered.slice(-AVTONET_HTTP_LOGS_LIMIT);
  }, [events]);
}

/** Matches backend ``AVTONET_LOOKAHEAD_BATCH_SIZE`` (same as bolha ``LOOKAHEAD_ADS`` = 20). */
export const AVTONET_LOOKAHEAD_COUNT = 20;

export function useAdminUsers(enabled: boolean) {
  return useQuery<AdminUser[]>({
    queryKey: adminKeys.users,
    queryFn: async () => {
      const { data } = await api.get<AdminUser[]>("/admin/users");
      return data;
    },
    enabled,
    refetchInterval: 30_000,
  });
}

export type BolhaProgressiveRow = {
  ad_id: number;
  zone: string;
  display_status: string;
  outcome: string | null;
  http_status: number | null;
  gtm_ad_status: string | null;
  fetched_at: string | null;
  inactive_age_seconds: number | null;
  detail: string | null;
  pipeline_status: string | null;
};

export type BolhaProgressiveState = {
  look_ahead_count: number;
  last_working_ad_id: number;
  last_working_at: string | null;
  scan_anchor_ad_id: number;
  last_homepage_max: number;
  last_fetch_high_water: number;
  last_fetch_started_at: string | null;
  db_numeric_max: number;
  lookahead_rows: BolhaProgressiveRow[];
  pivot_row: BolhaProgressiveRow;
  tail_rows: BolhaProgressiveRow[];
};

export type BolhaAdStateRow = {
  ad_id: number;
  status: string;
  last_lookahead_at: string | null;
  first_fallback_scrape_at: string | null;
  last_fallback_scrape_at: string | null;
  last_outcome: string | null;
  last_detail: string | null;
  created_at: string;
  updated_at: string;
};

export type BolhaAdScrapeEntry = {
  offset_seconds: number;
  at: string;
  source: string;
  result: string;
  http_status: number | null;
  detail: string | null;
};

export type BolhaAdRow = {
  ad_id: number;
  status: string;
  created_at: string;
  updated_at: string;
  scrapes: BolhaAdScrapeEntry[];
};

export type AvtonetAdScrapeEntry = BolhaAdScrapeEntry;
export type AvtonetAdRow = BolhaAdRow;
export type AvtonetAdMatchResponse = BolhaAdMatchResponse;

export type AvtonetScrapeState = {
  last_working_ad_id: number;
  last_working_at: string | null;
  last_batch_started_at: string | null;
  lookahead_batch_size: number;
  probe_delay_seconds: number;
  fetch_mode: string;
  scraperapi_enabled: boolean;
};

/** Bolha iAPI probe URL (works for any ad ID without knowing the slug). */
export function bolhaAdUrl(adId: number): string {
  return `https://iapi.bolha.com/avtomobili/progressive-scrape-oglas-${adId}`;
}

export function avtonetAdUrl(adId: number): string {
  return `https://www.avto.net/Ads/details.asp?id=${adId}`;
}

export function bolhaAdsQueryKey(limit: number) {
  return [...adminKeys.bolhaAds, limit] as const;
}

function normalizeAdId(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function parseScrapeEntry(
  raw: unknown,
  createdAtIso: string,
): BolhaAdScrapeEntry | null {
  if (!raw || typeof raw !== "object") return null;
  const s = raw as Record<string, unknown>;
  const at = typeof s.at === "string" ? s.at : null;
  const result = typeof s.result === "string" ? s.result : null;
  const source = typeof s.source === "string" ? s.source : null;
  if (!at || !result || !source) return null;
  const origin = Date.parse(createdAtIso);
  const atMs = Date.parse(at);
  const offset_seconds =
    Number.isFinite(origin) && Number.isFinite(atMs)
      ? Math.round((atMs - origin) / 100) / 10
      : 0;
  const http_status =
    typeof s.http_status === "number"
      ? s.http_status
      : typeof s.http_status === "string" && s.http_status !== ""
        ? Number(s.http_status)
        : null;
  return {
    offset_seconds,
    at,
    source,
    result,
    http_status:
      http_status != null && Number.isFinite(http_status) ? http_status : null,
    detail: typeof s.detail === "string" ? s.detail : null,
  };
}

function parseBolhaAdRow(raw: unknown): BolhaAdRow | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as BolhaAdRow;
  const adId = normalizeAdId(row.ad_id);
  if (adId == null || !Array.isArray(row.scrapes)) return null;
  return { ...row, ad_id: adId };
}

/** Apply one ``bolha_ad_update`` event to the React Query cache (patch or legacy full row). */
export function applyBolhaAdWsEvent(
  qc: QueryClient,
  limit: number,
  ev: ScraperEvent,
): boolean {
  if (ev.kind !== "bolha_ad_update" || !ev.data) return false;
  if (ev.data._truncated) return false;

  const legacyRow = ev.data.row != null ? parseBolhaAdRow(ev.data.row) : null;
  if (legacyRow) {
    qc.setQueryData<BolhaAdRow[]>(bolhaAdsQueryKey(limit), (prev) => {
      if (!prev) return prev;
      const idx = prev.findIndex((x) => x.ad_id === legacyRow.ad_id);
      if (idx >= 0) {
        const next = prev.slice();
        next[idx] = legacyRow;
        return next;
      }
      return [legacyRow, ...prev]
        .sort((a, b) => b.ad_id - a.ad_id)
        .slice(0, limit);
    });
    return true;
  }

  const adId = normalizeAdId(ev.data.ad_id);
  const createdAt =
    typeof ev.data.created_at === "string" ? ev.data.created_at : null;
  const scrape = createdAt ? parseScrapeEntry(ev.data.scrape, createdAt) : null;
  if (
    adId == null ||
    !scrape ||
    typeof ev.data.status !== "string" ||
    !createdAt
  )
    return false;

  const updatedAt =
    typeof ev.data.updated_at === "string" ? ev.data.updated_at : createdAt;

  qc.setQueryData<BolhaAdRow[]>(bolhaAdsQueryKey(limit), (prev) => {
    if (!prev) return prev;
    const idx = prev.findIndex((x) => x.ad_id === adId);
    if (idx >= 0) {
      const cur = prev[idx];
      if (cur.scrapes.some((s) => s.at === scrape.at)) return prev;
      const next = prev.slice();
      next[idx] = {
        ...cur,
        status: ev.data.status as string,
        updated_at: updatedAt,
        scrapes: [...cur.scrapes, scrape],
      };
      return next;
    }
    const row: BolhaAdRow = {
      ad_id: adId,
      status: ev.data.status as string,
      created_at: createdAt,
      updated_at: updatedAt,
      scrapes: [scrape],
    };
    return [row, ...prev].sort((a, b) => b.ad_id - a.ad_id).slice(0, limit);
  });
  return true;
}

/** Apply one ``avtonet_ad_update`` event to the React Query cache. */
export function applyAvtonetAdWsEvent(
  qc: QueryClient,
  limit: number,
  ev: ScraperEvent,
): boolean {
  if (ev.kind !== "avtonet_ad_update" || !ev.data) return false;
  if (ev.data._truncated) return false;

  const legacyRow = ev.data.row != null ? parseBolhaAdRow(ev.data.row) : null;
  if (legacyRow) {
    qc.setQueryData<AvtonetAdRow[]>(avtonetAdsQueryKey(limit), (prev) => {
      if (!prev) return prev;
      const idx = prev.findIndex((x) => x.ad_id === legacyRow.ad_id);
      if (idx >= 0) {
        const next = prev.slice();
        next[idx] = legacyRow;
        return next;
      }
      return [legacyRow, ...prev]
        .sort((a, b) => b.ad_id - a.ad_id)
        .slice(0, limit);
    });
    return true;
  }

  const adId = normalizeAdId(ev.data.ad_id);
  const createdAt =
    typeof ev.data.created_at === "string" ? ev.data.created_at : null;
  const scrape = createdAt ? parseScrapeEntry(ev.data.scrape, createdAt) : null;
  if (
    adId == null ||
    !scrape ||
    typeof ev.data.status !== "string" ||
    !createdAt
  )
    return false;

  const updatedAt =
    typeof ev.data.updated_at === "string" ? ev.data.updated_at : createdAt;

  qc.setQueryData<AvtonetAdRow[]>(avtonetAdsQueryKey(limit), (prev) => {
    if (!prev) return prev;
    const idx = prev.findIndex((x) => x.ad_id === adId);
    if (idx >= 0) {
      const cur = prev[idx];
      if (cur.scrapes.some((s) => s.at === scrape.at)) return prev;
      const next = prev.slice();
      next[idx] = {
        ...cur,
        status: ev.data.status as string,
        updated_at: updatedAt,
        scrapes: [...cur.scrapes, scrape],
      };
      return next;
    }
    const row: AvtonetAdRow = {
      ad_id: adId,
      status: ev.data.status as string,
      created_at: createdAt,
      updated_at: updatedAt,
      scrapes: [scrape],
    };
    return [row, ...prev].sort((a, b) => b.ad_id - a.ad_id).slice(0, limit);
  });
  return true;
}

export type BolhaPivotMeta = {
  lastWorkingId: number;
  scanAnchorId: number;
  lookaheadCount: number;
};

/** Track last-working / lookahead band from scraper WS events (no progressive-state HTTP). */
export function useBolhaPivotFromWs(
  enabled: boolean,
  events: ScraperEvent[],
): BolhaPivotMeta {
  return useMemo(() => {
    if (!enabled) {
      return {
        lastWorkingId: 0,
        scanAnchorId: 0,
        lookaheadCount: BOLHA_LOOKAHEAD_COUNT,
      };
    }
    let lastWorkingId = 0;
    let scanAnchorId = 0;
    for (const ev of events) {
      if (ev.kind === "bolha_progressive_tick") {
        const lw = ev.data?.last_working_ad_id;
        if (typeof lw === "number") lastWorkingId = lw;
      }
      if (ev.kind === "bolha_scout_done") {
        const na = ev.data?.new_anchor;
        if (typeof na === "number") {
          lastWorkingId = na;
          scanAnchorId = na;
        }
      }
    }
    return {
      lastWorkingId,
      scanAnchorId,
      lookaheadCount: BOLHA_LOOKAHEAD_COUNT,
    };
  }, [enabled, events]);
}

/** Live bolha_ad_update handler: immediate per-event delivery + replay after initial load. */
export function useBolhaAdsWsSync(
  enabled: boolean,
  limit: number,
  events: ScraperEvent[],
  adsReady: boolean,
  socketConnected: boolean,
): void {
  const qc = useQueryClient();
  const seenIds = useRef(new Set<string>());
  const wasConnected = useRef(false);
  const adsReadyRef = useRef(adsReady);

  useEffect(() => {
    adsReadyRef.current = adsReady;
  }, [adsReady]);

  const applyOne = useCallback(
    (ev: ScraperEvent) => {
      if (!adsReadyRef.current || seenIds.current.has(ev.id)) return;
      if (ev.kind !== "bolha_ad_update") return;
      if (applyBolhaAdWsEvent(qc, limit, ev)) {
        seenIds.current.add(ev.id);
      }
    },
    [qc, limit],
  );

  useEffect(() => {
    if (!enabled) {
      seenIds.current.clear();
      wasConnected.current = false;
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    if (socketConnected && !wasConnected.current) {
      seenIds.current.clear();
    }
    wasConnected.current = socketConnected;
  }, [enabled, socketConnected]);

  useEffect(() => {
    if (!enabled || !adsReady) return;
    for (const ev of events) {
      applyOne(ev);
    }
  }, [enabled, adsReady, events, applyOne]);

  useEffect(() => {
    if (!enabled) return;
    return subscribeScraperEvents(applyOne);
  }, [enabled, applyOne]);
}

export function useBolhaAds(enabled: boolean, limit = BOLHA_ADS_TOP_LIMIT) {
  return useQuery<BolhaAdRow[]>({
    queryKey: bolhaAdsQueryKey(limit),
    queryFn: async () => {
      const { data } = await api.get<BolhaAdRow[]>("/admin/bolha/ads", {
        params: { limit },
      });
      return data;
    },
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function avtonetAdsQueryKey(limit: number) {
  return [...adminKeys.avtonetAds, limit] as const;
}

export function useAvtonetPivotFromWs(
  enabled: boolean,
  events: ScraperEvent[],
): BolhaPivotMeta {
  return useMemo(() => {
    if (!enabled) {
      return {
        lastWorkingId: 0,
        scanAnchorId: 0,
        lookaheadCount: AVTONET_LOOKAHEAD_COUNT,
      };
    }
    let lastWorkingId = 0;
    let scanAnchorId = 0;
    for (const ev of events) {
      if (ev.kind === "avtonet_progress_tick") {
        const lw = ev.data?.last_working_ad_id;
        if (typeof lw === "number") lastWorkingId = lw;
        if (ev.data?.outcome === "success" && typeof ev.data?.ad_id === "number") {
          lastWorkingId = Math.max(lastWorkingId, ev.data.ad_id);
          scanAnchorId = ev.data.ad_id;
        }
      }
      if (ev.kind === "avtonet_scout_done") {
        const na = ev.data?.new_anchor;
        if (typeof na === "number") {
          lastWorkingId = na;
          scanAnchorId = na;
        }
      }
    }
    return {
      lastWorkingId,
      scanAnchorId,
      lookaheadCount: AVTONET_LOOKAHEAD_COUNT,
    };
  }, [enabled, events]);
}

export function useAvtonetAdsWsSync(
  enabled: boolean,
  limit: number,
  events: ScraperEvent[],
  adsReady: boolean,
  socketConnected: boolean,
): void {
  const qc = useQueryClient();
  const seenIds = useRef(new Set<string>());
  const wasConnected = useRef(false);
  const adsReadyRef = useRef(adsReady);

  useEffect(() => {
    adsReadyRef.current = adsReady;
  }, [adsReady]);

  const applyOne = useCallback(
    (ev: ScraperEvent) => {
      if (!adsReadyRef.current || seenIds.current.has(ev.id)) return;
      if (ev.kind !== "avtonet_ad_update") return;
      if (applyAvtonetAdWsEvent(qc, limit, ev)) {
        seenIds.current.add(ev.id);
      }
    },
    [qc, limit],
  );

  useEffect(() => {
    if (!enabled) {
      seenIds.current.clear();
      wasConnected.current = false;
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    if (socketConnected && !wasConnected.current) {
      seenIds.current.clear();
    }
    wasConnected.current = socketConnected;
  }, [enabled, socketConnected]);

  useEffect(() => {
    if (!enabled || !adsReady) return;
    for (const ev of events) {
      applyOne(ev);
    }
  }, [enabled, adsReady, events, applyOne]);

  useEffect(() => {
    if (!enabled) return;
    return subscribeScraperEvents(applyOne);
  }, [enabled, applyOne]);
}

export function useAvtonetAds(enabled: boolean, limit = AVTONET_ADS_TOP_LIMIT) {
  return useQuery<AvtonetAdRow[]>({
    queryKey: avtonetAdsQueryKey(limit),
    queryFn: async () => {
      const { data } = await api.get<AvtonetAdRow[]>("/admin/avtonet/ads", {
        params: { limit },
      });
      return data;
    },
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useAvtonetScrapeState(enabled: boolean) {
  return useQuery<AvtonetScrapeState>({
    queryKey: adminKeys.avtonetState,
    queryFn: async () => {
      const { data } = await api.get<AvtonetScrapeState>("/admin/avtonet/state");
      return data;
    },
    enabled,
    refetchInterval: enabled ? 5000 : false,
  });
}

const scraperEventListeners = new Set<(ev: ScraperEvent) => void>();

export function subscribeScraperEvents(
  listener: (ev: ScraperEvent) => void,
): () => void {
  scraperEventListeners.add(listener);
  return () => {
    scraperEventListeners.delete(listener);
  };
}

function notifyScraperEventListeners(ev: ScraperEvent): void {
  for (const listener of scraperEventListeners) {
    listener(ev);
  }
}

export function useBolhaAdStates(enabled: boolean, limit = 10_000) {
  return useQuery<BolhaAdStateRow[]>({
    queryKey: [...adminKeys.bolhaAdStates, limit] as const,
    queryFn: async () => {
      const { data } = await api.get<BolhaAdStateRow[]>(
        "/admin/bolha/ad-states",
        {
          params: { limit },
        },
      );
      return data;
    },
    enabled,
    refetchInterval: enabled ? 500 : false,
  });
}

export function useBolhaProgressiveState(enabled: boolean) {
  return useQuery<BolhaProgressiveState>({
    queryKey: adminKeys.bolhaProgressive,
    queryFn: async () => {
      const { data } = await api.get<BolhaProgressiveState>(
        "/admin/bolha/progressive-state",
      );
      return data;
    },
    enabled,
    refetchInterval: enabled ? 500 : false,
  });
}

export type AvtonetProgressiveState = BolhaProgressiveState;

export function useAvtonetProgressiveState(enabled: boolean) {
  return useQuery<AvtonetProgressiveState>({
    queryKey: adminKeys.avtonetProgressive,
    queryFn: async () => {
      const { data } = await api.get<AvtonetProgressiveState>(
        "/admin/avtonet/progressive-state",
      );
      return data;
    },
    enabled,
    refetchInterval: enabled ? 500 : false,
  });
}

export type AvtonetAdStateRow = BolhaAdStateRow;

export function useAvtonetAdStates(enabled: boolean, limit = 10_000) {
  return useQuery<AvtonetAdStateRow[]>({
    queryKey: [...adminKeys.avtonetAdStates, limit] as const,
    queryFn: async () => {
      const { data } = await api.get<AvtonetAdStateRow[]>(
        "/admin/avtonet/ad-states",
        { params: { limit } },
      );
      return data;
    },
    enabled,
    refetchInterval: enabled ? 500 : false,
  });
}

export const BOLHA_LISTING_SOURCE = "bolha.com";
export const AVTONET_LISTING_SOURCE = "avto.net";

export function adminListingsQueryKey(source?: string) {
  return source
    ? ([...adminKeys.listingsRoot, source] as const)
    : adminKeys.listingsRoot;
}

export function useAdminListings(
  enabled: boolean,
  options?: { source?: string; limit?: number },
) {
  const source = options?.source;
  const limit = options?.limit ?? 100;
  return useQuery<AdminListing[]>({
    queryKey: adminListingsQueryKey(source),
    queryFn: async () => {
      const { data } = await api.get<AdminListing[]>("/admin/listings", {
        params: { limit, ...(source ? { source } : {}) },
      });
      return data;
    },
    enabled,
    refetchInterval: 30_000,
  });
}

export function useScraperStatus(enabled: boolean) {
  return useQuery<ScraperStatus>({
    queryKey: adminKeys.scraperStatus,
    queryFn: async () => {
      const { data } = await api.get<ScraperStatus>("/admin/scraper/status");
      return data;
    },
    enabled,
  });
}

export function useTriggerScraper() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ queued: boolean; reason: string }>(
        "/admin/scraper/trigger",
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.scraperStatus });
      qc.invalidateQueries({ queryKey: adminKeys.listingsRoot });
      qc.invalidateQueries({ queryKey: adminKeys.bolhaProgressive });
      qc.invalidateQueries({ queryKey: adminKeys.bolhaAdStates });
      qc.invalidateQueries({ queryKey: adminKeys.bolhaAds });
      qc.invalidateQueries({ queryKey: adminKeys.avtonetAds });
      qc.invalidateQueries({ queryKey: adminKeys.avtonetState });
    },
  });
}

export function useRunSourceScrape() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (source: string) => {
      const { data } = await api.post<RunSourceResponse>(
        "/admin/scraper/run-source",
        {
          source,
        },
      );
      return data;
    },
    onSuccess: (_data, source) => {
      qc.invalidateQueries({ queryKey: adminKeys.scraperStatus });
      qc.invalidateQueries({ queryKey: adminKeys.listingsRoot });
      if (
        source === "bolha.com" ||
        source === "bolha.lookahead" ||
        source === "bolha.backfill" ||
        source === "bolha.scout"
      ) {
        qc.invalidateQueries({ queryKey: adminKeys.bolhaProgressive });
        qc.invalidateQueries({ queryKey: adminKeys.bolhaAdStates });
        qc.invalidateQueries({ queryKey: adminKeys.bolhaAds });
      }
      if (
        source === "avto.net" ||
        source === "avto.net.lookahead" ||
        source === "avto.net.scout"
      ) {
        qc.invalidateQueries({ queryKey: adminKeys.avtonetAds });
        qc.invalidateQueries({ queryKey: adminKeys.avtonetState });
      }
    },
  });
}

export function useMatchBolhaAd() {
  return useMutation({
    mutationFn: async (adId: number) => {
      const { data } = await api.post<BolhaAdMatchResponse>(
        `/admin/bolha/ads/${adId}/match`,
      );
      return data;
    },
  });
}

export function useMatchAvtonetAd() {
  return useMutation({
    mutationFn: async (adId: number) => {
      const { data } = await api.post<AvtonetAdMatchResponse>(
        `/admin/avtonet/ads/${adId}/match`,
      );
      return data;
    },
  });
}

type WsSnapshot = {
  kind: "snapshot";
  events: ScraperEvent[];
  status: ScraperStatus;
};
type WsEvent = { kind: "event"; event: ScraperEvent };
type WsStatus = { kind: "status"; status: ScraperStatus };
type WsMessage = WsSnapshot | WsEvent | WsStatus;

export type ScraperLive = {
  status: ScraperStatus | null;
  events: ScraperEvent[];
  socketConnected: boolean;
  clearEvents: () => void;
};

const MAX_LIVE_EVENTS = 200;

function wsUrlFor(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

// One admin scraper WebSocket for the whole tab. React StrictMode runs
// mount → cleanup → mount back-to-back in dev; debouncing teardown avoids
// closing the socket between those passes (which made Vite's ws proxy log
// write EPIPE when the backend kept sending status pings).
const scraperLiveBus = (() => {
  let refcount = 0;
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let disconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let status: ScraperStatus | null = null;
  let events: ScraperEvent[] = [];
  let socketConnected = false;
  const listeners = new Set<() => void>();

  const notify = () => {
    for (const listener of listeners) {
      listener();
    }
  };

  const appendEvent = (incoming: ScraperEvent) => {
    if (events.some((existing) => existing.id === incoming.id)) {
      return;
    }
    const next = events.concat(incoming);
    events =
      next.length > MAX_LIVE_EVENTS
        ? next.slice(next.length - MAX_LIVE_EVENTS)
        : next;
  };

  const handleMessage = (msg: WsMessage) => {
    if (msg.kind === "snapshot") {
      status = msg.status;
      events = msg.events.slice(-MAX_LIVE_EVENTS);
      for (const ev of events) {
        notifyScraperEventListeners(ev);
      }
    } else if (msg.kind === "event") {
      notifyScraperEventListeners(msg.event);
      appendEvent(msg.event);
    } else if (msg.kind === "status") {
      status = msg.status;
    }
    notify();
  };

  const connect = () => {
    if (refcount === 0 || socket) return;
    const ws = new WebSocket(wsUrlFor("/api/admin/scraper/ws"));
    socket = ws;

    ws.onopen = () => {
      if (ws !== socket) return;
      socketConnected = true;
      notify();
    };
    ws.onclose = () => {
      if (ws !== socket) return;
      socketConnected = false;
      socket = null;
      notify();
      if (refcount > 0) {
        reconnectTimer = setTimeout(connect, 1500);
      }
    };
    ws.onerror = () => {
      // onclose handles reconnect.
    };
    ws.onmessage = (e) => {
      if (ws !== socket) return;
      try {
        handleMessage(JSON.parse(e.data) as WsMessage);
      } catch {
        // ignore malformed messages
      }
    };
  };

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    const ws = socket;
    socket = null;
    socketConnected = false;
    if (ws && ws.readyState <= WebSocket.OPEN) {
      ws.close();
    }
    notify();
  };

  return {
    subscribe(listener: () => void) {
      if (disconnectTimer) {
        clearTimeout(disconnectTimer);
        disconnectTimer = null;
      }
      refcount += 1;
      listeners.add(listener);
      if (refcount === 1) {
        connect();
      }
      listener();
      return () => {
        listeners.delete(listener);
        refcount -= 1;
        if (refcount === 0) {
          disconnectTimer = setTimeout(() => {
            disconnectTimer = null;
            if (refcount === 0) {
              disconnect();
            }
          }, 0);
        }
      };
    },
    getStatus: () => status,
    getEvents: () => events,
    getSocketConnected: () => socketConnected,
    clearEvents() {
      events = [];
      notify();
    },
  };
})();

export function useScraperLive(enabled: boolean): ScraperLive {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    return scraperLiveBus.subscribe(() => {
      setTick((n) => n + 1);
    });
  }, [enabled]);

  const clearEvents = useCallback(() => {
    scraperLiveBus.clearEvents();
  }, []);

  if (!enabled) {
    return {
      status: null,
      events: [],
      socketConnected: false,
      clearEvents,
    };
  }

  return {
    status: scraperLiveBus.getStatus(),
    events: scraperLiveBus.getEvents(),
    socketConnected: scraperLiveBus.getSocketConnected(),
    clearEvents,
  };
}
