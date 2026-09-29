import { useEffect, useRef, useState } from 'react'

// Minimal shape of the Google Identity Services global we actually use.
// Only identity/sign-in — no Gmail/Drive/Calendar/Contacts scopes are ever
// requested (see CLAUDE.md Phase 1G section 7).
interface GoogleIdentityServices {
  accounts: {
    id: {
      initialize: (config: {
        client_id: string
        callback: (response: { credential: string }) => void
      }) => void
      renderButton: (element: HTMLElement, options: Record<string, unknown>) => void
    }
  }
}

declare global {
  interface Window {
    google?: GoogleIdentityServices
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const GSI_SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

function loadGsiScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve()
      return
    }
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SCRIPT_SRC}"]`)
    if (existing) {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('load-failed')))
      return
    }
    const script = document.createElement('script')
    script.src = GSI_SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('load-failed'))
    document.head.appendChild(script)
  })
}

interface GoogleSignInButtonProps {
  onCredential: (credential: string) => void
}

/** Renders Google's own "Continue with Google" button via Google Identity
 * Services. TradeLens never sees the user's Google password and never
 * trusts any identity field from this button directly — only the opaque
 * `credential` (a signed ID token) is forwarded to the backend, which
 * cryptographically verifies it (see app/auth/google_verify.py). */
export function GoogleSignInButton({ onCredential }: GoogleSignInButtonProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const onCredentialRef = useRef(onCredential)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    onCredentialRef.current = onCredential
  }, [onCredential])

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return
    let cancelled = false

    loadGsiScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google) return
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => onCredentialRef.current(response.credential),
        })
        window.google.accounts.id.renderButton(containerRef.current, {
          theme: 'outline',
          size: 'large',
          width: 320,
          text: 'continue_with',
        })
      })
      .catch(() => {
        if (!cancelled) setError('Could not load Google Sign-In.')
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (!GOOGLE_CLIENT_ID) {
    return (
      <button
        type="button"
        disabled
        title="Set VITE_GOOGLE_CLIENT_ID to enable Google sign-in"
        className="w-full rounded-md border border-[var(--border)] px-4 py-2.5 text-sm font-medium text-[var(--text-tertiary)]"
      >
        Continue with Google
      </button>
    )
  }

  if (error) {
    return <p className="text-xs text-[var(--negative)]">{error}</p>
  }

  return <div ref={containerRef} data-testid="google-signin-button" />
}
