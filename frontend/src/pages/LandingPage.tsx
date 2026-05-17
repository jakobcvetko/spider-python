import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { MarketingFooter } from '../components/MarketingFooter'
import { useMarketingLocale } from '../hooks/useMarketingLocale'
import { useHeroParallax } from '../hooks/useHeroParallax'
import { useRevealOnScroll } from '../hooks/useRevealOnScroll'

const HERO_IMAGE =
  'https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=2400&q=80'

const WORKFLOW_IMAGE =
  'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=1600&q=80'

function RevealSection({
  children,
  className = '',
  delay = 0,
}: {
  children: ReactNode
  className?: string
  delay?: number
}) {
  const { ref, visible } = useRevealOnScroll<HTMLElement>()
  return (
    <section
      ref={ref}
      className={`landing-reveal ${visible ? 'landing-reveal--visible' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </section>
  )
}

export default function LandingPage() {
  const { t } = useMarketingLocale()
  const copy = t.landing

  useHeroParallax()

  return (
    <div className="landing-page bg-zinc-950 text-zinc-100">
      <header className="landing-header fixed inset-x-0 top-0 z-40 flex items-center justify-between px-5 py-4 sm:px-8">
        <Link to="/" className="flex items-baseline gap-2">
          <span className="font-display text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            Spider
          </span>
          <span className="hidden text-xs font-medium uppercase tracking-[0.2em] text-amber-400/80 sm:inline">
            {t.brandTagline}
          </span>
        </Link>
        <Link
          to="/login"
          className="rounded-full border border-white/20 bg-white/5 px-4 py-1.5 text-sm font-medium text-white backdrop-blur-sm transition hover:border-amber-400/50 hover:bg-amber-400/10"
        >
          {t.signIn}
        </Link>
      </header>

      <section className="landing-hero relative min-h-svh w-full overflow-hidden">
        <div
          className="landing-hero-bg absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${HERO_IMAGE})` }}
          aria-hidden
        />
        <div className="absolute inset-0 bg-gradient-to-r from-zinc-950 via-zinc-950/85 to-zinc-950/35" />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-zinc-950/40" />

        <div className="relative z-10 mx-auto flex min-h-svh max-w-7xl flex-col justify-end px-5 pb-10 pt-24 sm:px-8 sm:pb-14 lg:pb-20">
          <div className="landing-hero-copy max-w-2xl">
            <p className="landing-hero-enter mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-amber-400">
              {copy.heroEyebrow}
            </p>
            <h1 className="landing-hero-enter landing-hero-enter--2 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-6xl">
              {copy.heroTitle}
            </h1>
            <p className="landing-hero-enter landing-hero-enter--3 mt-4 max-w-lg text-base leading-relaxed text-zinc-300 sm:text-lg">
              {copy.heroBody}
            </p>
            <div className="landing-hero-enter landing-hero-enter--4 mt-8 flex flex-wrap items-center gap-4">
              <Link
                to="/login"
                className="inline-flex items-center justify-center rounded-full bg-amber-500 px-7 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-amber-400"
              >
                {t.signIn}
              </Link>
              <Link
                to="/register"
                className="inline-flex items-center justify-center rounded-full border border-white/25 px-7 py-3 text-sm font-semibold text-white transition hover:border-amber-400/50 hover:bg-white/5"
              >
                {t.createAccount}
              </Link>
            </div>
            <div className="landing-hero-enter landing-hero-enter--5 mt-10 flex flex-wrap items-center gap-6 text-sm text-zinc-400 sm:gap-8">
              <span className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                {copy.sourceBolha}
              </span>
              <span className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                {copy.sourceAvtonet}
              </span>
              <span className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                {copy.sourceScrapers}
              </span>
            </div>
          </div>
        </div>
      </section>

      <RevealSection className="border-t border-white/5 px-5 py-20 sm:px-8 sm:py-28">
        <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-2 lg:items-center lg:gap-20">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-amber-400">
              {copy.sectionOneLabel}
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              {copy.sectionOneTitle}
            </h2>
            <p className="mt-4 max-w-lg text-lg leading-relaxed text-zinc-400">
              {copy.sectionOneBody}
            </p>
          </div>
          <ul className="space-y-6 border-l border-white/10 pl-8">
            <li>
              <p className="text-sm font-medium text-zinc-200">{copy.featureCarsTitle}</p>
              <p className="mt-1 text-sm text-zinc-500">{copy.featureCarsBody}</p>
            </li>
            <li>
              <p className="text-sm font-medium text-zinc-200">{copy.featureGoodsTitle}</p>
              <p className="mt-1 text-sm text-zinc-500">{copy.featureGoodsBody}</p>
            </li>
            <li>
              <p className="text-sm font-medium text-zinc-200">{copy.featureMatchesTitle}</p>
              <p className="mt-1 text-sm text-zinc-500">{copy.featureMatchesBody}</p>
            </li>
          </ul>
        </div>
      </RevealSection>

      <RevealSection className="relative overflow-hidden border-t border-white/5" delay={80}>
        <div
          className="absolute inset-0 bg-cover bg-center opacity-30"
          style={{ backgroundImage: `url(${WORKFLOW_IMAGE})` }}
          aria-hidden
        />
        <div className="absolute inset-0 bg-zinc-950/88" aria-hidden />
        <div className="relative px-5 py-20 sm:px-8 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-amber-400">
              {copy.sectionHowLabel}
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              {copy.sectionHowTitle}
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg leading-relaxed text-zinc-400">
              {copy.sectionHowBody}
            </p>
            <ol className="mt-12 grid gap-8 text-left sm:grid-cols-3 sm:gap-6">
              <li className="border-t border-amber-400/40 pt-4">
                <span className="font-display text-2xl text-amber-400">01</span>
                <p className="mt-2 font-medium text-white">{copy.step1Title}</p>
                <p className="mt-1 text-sm text-zinc-500">{copy.step1Body}</p>
              </li>
              <li className="border-t border-amber-400/40 pt-4">
                <span className="font-display text-2xl text-amber-400">02</span>
                <p className="mt-2 font-medium text-white">{copy.step2Title}</p>
                <p className="mt-1 text-sm text-zinc-500">{copy.step2Body}</p>
              </li>
              <li className="border-t border-amber-400/40 pt-4">
                <span className="font-display text-2xl text-amber-400">03</span>
                <p className="mt-2 font-medium text-white">{copy.step3Title}</p>
                <p className="mt-1 text-sm text-zinc-500">{copy.step3Body}</p>
              </li>
            </ol>
          </div>
        </div>
      </RevealSection>

      <RevealSection className="border-t border-white/5 px-5 py-20 sm:px-8 sm:py-24" delay={120}>
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-8 sm:flex-row sm:items-center">
          <div>
            <h2 className="font-display text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              {copy.ctaTitle}
            </h2>
            <p className="mt-2 text-zinc-400">{copy.ctaBody}</p>
          </div>
          <Link
            to="/register"
            className="inline-flex shrink-0 items-center justify-center rounded-full bg-amber-500 px-8 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-amber-400"
          >
            {copy.ctaButton}
          </Link>
        </div>
      </RevealSection>

      <MarketingFooter />
    </div>
  )
}
