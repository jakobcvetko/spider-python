import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useMarketingLocale } from '../hooks/useMarketingLocale'
import { getErrorMessage, useRegister } from '../lib/auth'
import { DASHBOARD_PATH } from '../lib/routes'
import { Button, Input } from './ui'

export function RegisterForm() {
  const navigate = useNavigate()
  const register = useRegister()
  const { t } = useMarketingLocale()
  const copy = t.register

  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await register.mutateAsync({
        email,
        password,
        display_name: displayName.trim() || undefined,
      })
      navigate(DASHBOARD_PATH, { replace: true })
    } catch (err) {
      setError(getErrorMessage(err, copy.errorFallback))
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
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
        label={copy.businessName}
        type="text"
        autoComplete="organization"
        value={displayName}
        onChange={(e) => setDisplayName(e.target.value)}
        className="landing-input"
      />
      <Input
        label={copy.password}
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="landing-input"
      />
      <p className="text-xs text-zinc-500">{copy.passwordHint}</p>
      {error && <p className="text-sm text-red-300">{error}</p>}
      <Button type="submit" loading={register.isPending} className="landing-submit w-full">
        {copy.submit}
      </Button>
      <p className="text-center text-sm text-zinc-400">
        {copy.hasAccount}{' '}
        <Link to="/login" className="font-medium text-amber-400 hover:text-amber-300">
          {copy.signInLink}
        </Link>
      </p>
    </form>
  )
}
