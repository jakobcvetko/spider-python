import { useEffect } from 'react'

export function useHeroParallax(selector = '.landing-hero-bg') {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const el = document.querySelector<HTMLElement>(selector)
    if (!el) return

    let frame = 0
    const onScroll = () => {
      if (frame) return
      frame = requestAnimationFrame(() => {
        frame = 0
        const hero = el.closest('.landing-hero')
        if (!hero) return
        const rect = hero.getBoundingClientRect()
        const progress = Math.min(1, Math.max(0, -rect.top / rect.height))
        el.style.transform = `scale(1.06) translateY(${progress * 40}px)`
      })
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [selector])
}
