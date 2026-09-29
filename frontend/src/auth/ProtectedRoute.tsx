import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

/** Redirects unauthenticated users to /login, preserving the intended
 * destination via React Router's internal location state (never a raw
 * user-controlled URL/query param) — so there is no open-redirect surface:
 * LoginPage only ever navigates back to a `Location` object this app
 * itself produced, never to an arbitrary string. */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--text-tertiary)]">
        Loading…
      </div>
    )
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
