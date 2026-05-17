import { useContext } from 'react'

import { MarketingLocaleContext } from '../context/marketing-locale-context'

export function useMarketingLocale() {
  const ctx = useContext(MarketingLocaleContext)
  if (!ctx) {
    throw new Error('useMarketingLocale must be used within MarketingLocaleProvider')
  }
  return ctx
}
