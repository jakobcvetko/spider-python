import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useMe } from '../lib/auth'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { data, isLoading } = useMe()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-400">
        Loading…
      </div>
    )
  }

  if (!data) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <>{children}</>
}
