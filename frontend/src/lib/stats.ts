import { useQuery } from '@tanstack/react-query'

import { api } from './api'

export type DailyMatchCount = {
  date: string
  count: number
}

export type DailyMatches = {
  days: DailyMatchCount[]
  total: number
}

export const statsKeys = {
  dailyMatches: (days: number) => ['stats', 'daily-matches', days] as const,
}

export function useDailyMatches(enabled: boolean, days = 14) {
  return useQuery<DailyMatches>({
    queryKey: statsKeys.dailyMatches(days),
    queryFn: async () => {
      const { data } = await api.get<DailyMatches>('/stats/daily-matches', {
        params: { days },
      })
      return data
    },
    enabled,
    refetchInterval: 60_000,
  })
}
