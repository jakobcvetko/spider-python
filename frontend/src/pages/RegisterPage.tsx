import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { Button, Input, PageShell } from '../components/ui'
import { getErrorMessage, useMe, useRegister } from '../lib/auth'

export default function RegisterPage() {
  const navigate = useNavigate()
  const me = useMe()
  const register = useRegister()

  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (me.data) {
    return <Navigate to="/" replace />
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await register.mutateAsync({
        email,
        password,
        display_name: displayName.trim() || undefined,
      })
      navigate('/', { replace: true })
    } catch (err) {
      setError(getErrorMessage(err, 'Could not create account'))
    }
  }

  return (
    <PageShell>
      <div className="mx-auto max-w-md space-y-4 pt-8 sm:pt-12">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Create account</h1>
          <p className="mt-1 text-sm text-zinc-500">It only takes a second.</p>
        </div>
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
              label="Display name (optional)"
              type="text"
              autoComplete="nickname"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
            <Input
              label="Password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p className="text-xs text-zinc-500">Use at least 8 characters.</p>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" loading={register.isPending} className="w-full">
              Create account
            </Button>
          </form>
        <p className="text-sm text-zinc-500">
            Already have an account?{' '}
            <Link to="/login" className="text-indigo-600 hover:text-indigo-700">
              Sign in
            </Link>
          </p>
        </div>
    </PageShell>
  )
}
