import { forwardRef } from 'react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'danger'
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', loading, className = '', children, disabled, ...rest },
  ref,
) {
  const base =
    'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-950 disabled:opacity-50 disabled:cursor-not-allowed'
  const variants: Record<string, string> = {
    primary:
      'bg-indigo-500 text-white hover:bg-indigo-400 focus:ring-indigo-400',
    ghost:
      'bg-transparent text-zinc-100 hover:bg-zinc-800 focus:ring-zinc-500',
    danger:
      'bg-red-500/90 text-white hover:bg-red-500 focus:ring-red-400',
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
        <span className="mb-1 block text-sm font-medium text-zinc-300">{label}</span>
      )}
      <input
        ref={ref}
        id={id}
        className={`block w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 ${className}`}
        {...rest}
      />
      {error && <span className="mt-1 block text-xs text-red-400">{error}</span>}
    </label>
  )
})

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-sm backdrop-blur ${className}`}
    >
      {children}
    </div>
  )
}

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-5xl px-4 py-8">{children}</div>
    </div>
  )
}
