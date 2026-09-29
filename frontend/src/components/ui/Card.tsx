import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
}

export function Card({ children, className = '', ...rest }: CardProps) {
  return (
    <div
      className={`bg-[var(--surface-1)] border border-[var(--border)] rounded-md shadow-[var(--shadow-1)] ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
      {children}
    </div>
  )
}
