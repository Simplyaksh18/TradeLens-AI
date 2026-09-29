import { AlertTriangle, Inbox, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '../../api/client'

export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-2" role="status" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-4 rounded bg-[var(--surface-2)]" style={{ width: `${85 - i * 12}%` }} />
      ))}
    </div>
  )
}

export function NothingSelectedState({ message }: { message: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-[var(--text-secondary)]">
      <Inbox size={28} aria-hidden="true" />
      <p className="text-sm">{message}</p>
    </div>
  )
}

export function NoDataState({ message }: { message: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-[var(--text-secondary)]">
      <SearchX size={28} aria-hidden="true" />
      <p className="text-sm">{message}</p>
    </div>
  )
}

export function ApiErrorState({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? error.message : 'Something went wrong while contacting the TradeLens API.'
  const code = error instanceof ApiError ? error.code : undefined
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-2 rounded-md border border-[var(--negative)]/30 bg-[var(--negative-soft)] py-10 text-center"
    >
      <AlertTriangle size={26} className="text-[var(--negative)]" aria-hidden="true" />
      <p className="text-sm font-medium text-[var(--negative)]">{message}</p>
      {code && <p className="text-xs text-[var(--text-tertiary)] font-mono-tabular">{code}</p>}
    </div>
  )
}

export function InsufficientHistoryState({ missing }: { missing: string[] }) {
  return (
    <div className="rounded-md border border-[var(--warning)]/30 bg-[var(--warning-soft)] px-4 py-3 text-sm text-[var(--warning)]">
      <p className="font-medium">Not enough history to evaluate this strategy.</p>
      {missing.length > 0 && <p className="mt-1 text-xs opacity-90">Missing: {missing.join(' · ')}</p>}
    </div>
  )
}
