import { createContext } from 'react'

import type { MarketingCopy, MarketingLocale } from '../lib/marketing-i18n'

export type MarketingLocaleContextValue = {
  locale: MarketingLocale
  setLocale: (locale: MarketingLocale) => void
  t: MarketingCopy
}

export const MarketingLocaleContext = createContext<MarketingLocaleContextValue | null>(null)
