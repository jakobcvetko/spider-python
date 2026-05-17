import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import {
  MARKETING_LOCALE_STORAGE_KEY,
  marketingCopy,
  readStoredMarketingLocale,
  type MarketingLocale,
} from '../lib/marketing-i18n'
import { MarketingLocaleContext } from './marketing-locale-context'

export function MarketingLocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<MarketingLocale>(readStoredMarketingLocale)

  const setLocale = useCallback((next: MarketingLocale) => {
    setLocaleState(next)
    try {
      localStorage.setItem(MARKETING_LOCALE_STORAGE_KEY, next)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: marketingCopy[locale],
    }),
    [locale, setLocale],
  )

  return (
    <MarketingLocaleContext.Provider value={value}>{children}</MarketingLocaleContext.Provider>
  )
}
