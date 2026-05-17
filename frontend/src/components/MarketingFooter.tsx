import { useMarketingLocale } from '../hooks/useMarketingLocale'

export function MarketingFooter() {
  const { locale, setLocale, t } = useMarketingLocale()

  return (
    <footer className="border-t border-white/5 px-5 py-8 sm:px-8">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 text-center sm:flex-row sm:text-left">
        <p className="text-xs text-zinc-600">{t.landing.footer}</p>
        {locale === 'sl' ? (
          <button
            type="button"
            onClick={() => setLocale('en')}
            className="rounded px-2 py-1 text-xs font-medium text-zinc-400 transition hover:bg-white/5 hover:text-amber-400"
          >
            {t.switchToEnglish}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setLocale('sl')}
            className="rounded px-2 py-1 text-xs font-medium text-zinc-400 transition hover:bg-white/5 hover:text-amber-400"
          >
            {t.switchToSlovenian}
          </button>
        )}
      </div>
    </footer>
  )
}
