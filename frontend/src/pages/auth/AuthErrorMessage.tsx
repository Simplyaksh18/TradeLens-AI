import { AlertCircle } from 'lucide-react'

export function AuthErrorMessage({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="flex items-start gap-2 rounded-md border border-[var(--negative)]/30 bg-[var(--negative-soft)] px-3 py-2 text-sm text-[var(--negative)]"
    >
      <AlertCircle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </p>
  )
}
