import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, type Location } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import { GoogleSignInButton } from '../../auth/GoogleSignInButton'
import { AuthSplitLayout } from './AuthSplitLayout'
import { AuthTextField } from './AuthTextField'
import { AuthDivider } from './AuthDivider'
import { AuthErrorMessage } from './AuthErrorMessage'
import { ApiError } from '../../api/client'

export default function LoginPage() {
  const { login, loginWithGoogle } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Only ever navigate to a Location object this app produced (via
  // ProtectedRoute's `state`), never a raw string from the URL — no
  // open-redirect surface.
  const from = (location.state as { from?: Location } | null)?.from
  const destination = from ? { pathname: from.pathname, search: from.search } : '/'

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login({ email, password })
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleGoogleCredential(credential: string) {
    setError(null)
    try {
      await loginWithGoogle(credential)
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Google sign-in failed. Please try again.')
    }
  }

  return (
    <AuthSplitLayout>
      <h2 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">Welcome back</h2>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">Sign in to continue your research.</p>

      <div className="mt-6">
        <GoogleSignInButton onCredential={handleGoogleCredential} />
      </div>

      <AuthDivider />

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <AuthTextField
          id="login-email"
          label="Email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <AuthTextField
          id="login-password"
          label="Password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <AuthErrorMessage message={error} />}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-[var(--accent-strong)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100"
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-[var(--text-secondary)]">
        Don&apos;t have an account?{' '}
        <Link to="/signup" className="font-medium text-[var(--accent)] hover:underline">
          Create account
        </Link>
      </p>
    </AuthSplitLayout>
  )
}
