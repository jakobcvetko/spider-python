import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'

import { api } from './api'

export type User = {
  id: string
  email: string
  display_name: string | null
  created_at: string
}

export type RegisterPayload = {
  email: string
  password: string
  display_name?: string
}

export type LoginPayload = {
  email: string
  password: string
}

export const authKeys = {
  me: ['auth', 'me'] as const,
}

export function useMe() {
  return useQuery<User | null>({
    queryKey: authKeys.me,
    queryFn: async () => {
      try {
        const { data } = await api.get<User>('/auth/me')
        return data
      } catch (err) {
        if (err instanceof AxiosError && err.response?.status === 401) {
          return null
        }
        throw err
      }
    },
    staleTime: 30_000,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: LoginPayload) => {
      const { data } = await api.post<User>('/auth/login', payload)
      return data
    },
    onSuccess: (user) => {
      qc.setQueryData(authKeys.me, user)
    },
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: RegisterPayload) => {
      const { data } = await api.post<User>('/auth/register', payload)
      return data
    },
    onSuccess: (user) => {
      qc.setQueryData(authKeys.me, user)
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.post('/auth/logout')
    },
    onSuccess: () => {
      qc.setQueryData(authKeys.me, null)
      qc.removeQueries({ queryKey: ['listings'] })
    },
  })
}

export function getErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg as string
    return err.message
  }
  if (err instanceof Error) return err.message
  return fallback
}
