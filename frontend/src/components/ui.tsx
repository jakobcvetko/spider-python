import { forwardRef, useEffect } from 'react'
import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from 'react'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'danger'
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', loading, className = '', children, disabled, ...rest },
  ref,
) {
  const base =
    'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-50 disabled:opacity-50 disabled:cursor-not-allowed'
  const variants: Record<string, string> = {
    primary:
      'bg-indigo-600 text-white hover:bg-indigo-500 focus:ring-indigo-500',
    ghost:
      'bg-transparent text-zinc-700 hover:bg-zinc-100 focus:ring-zinc-400',
    danger:
      'bg-red-600 text-white hover:bg-red-500 focus:ring-red-500',
  }
  return (
    <button
      ref={ref}
      className={`${base} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? 'Loading…' : children}
    </button>
  )
})

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, className = '', id, ...rest },
  ref,
) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1 block text-sm font-medium text-zinc-700">{label}</span>
      )}
      <input
        ref={ref}
        id={id}
        className={`block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 ${className}`}
        {...rest}
      />
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  )
})

/** Flat section wrapper — no card chrome (border/shadow/padding). */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`space-y-3 ${className}`}>{children}</section>
}

type TableFrameProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode
}

export const TableFrame = forwardRef<HTMLDivElement, TableFrameProps>(function TableFrame(
  { children, className = '', ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={`-mx-3 overflow-x-auto border-y border-zinc-200 sm:mx-0 ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
})

type ModalProps = {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

export function Modal({ open, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const titleId = 'modal-title'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-zinc-900/50"
        aria-label="Close dialog"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-md rounded-xl border border-zinc-200 bg-white p-5 shadow-xl sm:p-6"
      >
        <h2 id={titleId} className="mb-4 text-lg font-semibold tracking-tight text-zinc-900">
          {title}
        </h2>
        {children}
      </div>
    </div>
  )
}

export function PageShell({
  children,
  wide = false,
}: {
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900">
      <div
        className={`mx-auto w-full px-3 py-3 sm:px-4 sm:py-4 ${wide ? 'max-w-[90rem]' : 'max-w-6xl'}`}
      >
        {children}
      </div>
    </div>
  )
}
