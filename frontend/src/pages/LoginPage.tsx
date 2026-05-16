import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { Button, Card, Input, PageShell } from '../components/ui'
import { getErrorMessage, useLogin, useMe } from '../lib/auth'

type LocationState = { from?: { pathname?: string } } | null

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const me = useMe()
  const login = useLogin()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (me.data) {
    return <Navigate to="/" replace />
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login.mutateAsync({ email, password })
      const next = (location.state as LocationState)?.from?.pathname || '/'
      navigate(next, { replace: true })
    } catch (err) {
      setError(getErrorMessage(err, 'Could not sign in'))
    }
  }

  return (
    <PageShell>
      <div className="mx-auto max-w-md pt-16">
        <Card>
          <h1 className="mb-1 text-2xl font-semibold tracking-tight">Sign in</h1>
          <p className="mb-6 text-sm text-zinc-400">Welcome back to Spider.</p>
          <form onSubmit={onSubmit} className="space-y-4">
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              minLength={1}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" loading={login.isPending} className="w-full">
              Sign in
            </Button>
          </form>
          <p className="mt-6 text-sm text-zinc-400">
            New here?{' '}
            <Link to="/register" className="text-indigo-600 hover:text-indigo-700">
              Create an account
            </Link>
          </p>
        </Card>
      </div>
    </PageShell>
  )
}
