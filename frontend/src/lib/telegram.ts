import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './api'

export type TelegramStatus = {
  connected: boolean
  username: string | null
  linked_at: string | null
  notifications_enabled: boolean
}

export type TelegramLink = {
  deep_link_url: string
  expires_at: string
}

export const telegramKeys = {
  status: ['telegram', 'status'] as const,
}

export function useTelegramStatus(enabled = true, refetchInterval?: number | false) {
  return useQuery<TelegramStatus>({
    queryKey: telegramKeys.status,
    queryFn: async () => {
      const { data } = await api.get<TelegramStatus>('/telegram/status')
      return data
    },
    enabled,
    refetchInterval,
  })
}

export function useTelegramLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TelegramLink>('/telegram/link')
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: telegramKeys.status })
    },
  })
}

export function useTelegramDisconnect() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.delete('/telegram')
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: telegramKeys.status })
    },
  })
}

export function useTelegramTest() {
  return useMutation({
    mutationFn: async () => {
      await api.post('/telegram/test')
    },
  })
}
