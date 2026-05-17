import { Navigate } from 'react-router-dom'

import { AuthPageShell } from '../components/AuthPageShell'
import { RegisterForm } from '../components/RegisterForm'
import { useMarketingLocale } from '../hooks/useMarketingLocale'
import { useMe } from '../lib/auth'
import { DASHBOARD_PATH } from '../lib/routes'

export default function RegisterPage() {
  const me = useMe()
  const { t } = useMarketingLocale()

  if (me.data) {
    return <Navigate to={DASHBOARD_PATH} replace />
  }

  return (
    <AuthPageShell title={t.register.title} description={t.register.description}>
      <RegisterForm />
    </AuthPageShell>
  )
}
