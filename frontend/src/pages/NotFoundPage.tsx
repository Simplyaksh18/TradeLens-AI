import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <Compass size={32} className="text-[var(--text-tertiary)]" aria-hidden="true" />
      <h1 className="text-lg font-semibold">Research route not found</h1>
      <p className="max-w-sm text-sm text-[var(--text-secondary)]">
        The TradeLens page you're looking for doesn't exist.
      </p>
      <Link
        to="/"
        className="mt-2 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--accent-strong)]"
      >
        Return to Overview
      </Link>
    </div>
  )
}
