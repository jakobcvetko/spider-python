import { Navigate, useLocation } from 'react-router-dom'

import { AuthPageShell } from '../components/AuthPageShell'
import { LoginForm } from '../components/LoginForm'
import { useMarketingLocale } from '../hooks/useMarketingLocale'
import { useMe } from '../lib/auth'
import { authReturnPath } from '../lib/routes'

type LocationState = { from?: { pathname?: string } } | null

export default function LoginPage() {
  const location = useLocation()
  const me = useMe()
  const { t } = useMarketingLocale()

  const returnTo = authReturnPath((location.state as LocationState)?.from?.pathname)

  if (me.data) {
    return <Navigate to={returnTo} replace />
  }

  return (
    <AuthPageShell title={t.login.title} description={t.login.description}>
      <LoginForm returnTo={returnTo} />
    </AuthPageShell>
  )
}
