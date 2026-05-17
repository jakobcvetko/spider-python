import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useMarketingLocale } from '../hooks/useMarketingLocale'
import { getErrorMessage, useLogin } from '../lib/auth'
import { DASHBOARD_PATH } from '../lib/routes'
import { Button, Input } from './ui'

type LoginFormProps = {
  returnTo?: string
  compact?: boolean
}

export function LoginForm({ returnTo = DASHBOARD_PATH, compact = false }: LoginFormProps) {
  const navigate = useNavigate()
  const login = useLogin()
  const { t } = useMarketingLocale()
  const copy = t.login

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login.mutateAsync({ email, password })
      navigate(returnTo, { replace: true })
    } catch (err) {
      setError(getErrorMessage(err, copy.errorFallback))
    }
  }

  return (
    <form onSubmit={onSubmit} className={compact ? 'space-y-3' : 'space-y-4'}>
      <Input
        label={copy.email}
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="landing-input"
      />
      <Input
        label={copy.password}
        type="password"
        autoComplete="current-password"
        required
        minLength={1}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="landing-input"
      />
      {error && <p className="text-sm text-red-300">{error}</p>}
      <Button type="submit" loading={login.isPending} className="landing-submit w-full">
        {copy.submit}
      </Button>
      <p className="text-center text-sm text-zinc-400">
        {copy.noAccount}{' '}
        <Link to="/register" className="font-medium text-amber-400 hover:text-amber-300">
          {copy.createAccountLink}
        </Link>
      </p>
    </form>
  )
}
