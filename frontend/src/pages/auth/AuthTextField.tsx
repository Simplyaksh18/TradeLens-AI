import type { InputHTMLAttributes } from 'react'

interface AuthTextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  id: string
}

/** Shared input styling for /login and /signup, so both pages visually
 * belong to the same authentication system rather than being styled
 * independently (label above input, consistent focus ring, consistent
 * spacing — see CLAUDE.md Phase 1F+ visual-consistency guidance). */
export function AuthTextField({ label, id, className, ...inputProps }: AuthTextFieldProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-xs font-medium text-[var(--text-tertiary)]">
        {label}
      </label>
      <input
        id={id}
        className={`w-full rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none transition-colors placeholder:text-[var(--text-tertiary)] focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 ${className ?? ''}`}
        {...inputProps}
      />
    </div>
  )
}
