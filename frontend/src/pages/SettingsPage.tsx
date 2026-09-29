import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/layout/PageHeader'
import { Card, SectionLabel } from '../components/ui/Card'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { Avatar } from '../components/layout/Avatar'
import { API_BASE_URL, ApiError } from '../api/client'
import { getHealth } from '../api/health'
import type { HealthResponse } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { greetingName } from '../utils/greeting'

export default function SettingsPage() {
  const { user, updateProfile, logout } = useAuth()
  const navigate = useNavigate()

  const [checkResult, setCheckResult] = useState<'idle' | 'checking' | 'ok' | 'failed'>('idle')
  const [health, setHealth] = useState<HealthResponse | null>(null)

  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function handleCheckConnection() {
    setCheckResult('checking')
    try {
      const result = await getHealth()
      setHealth(result)
      setCheckResult('ok')
    } catch {
      setCheckResult('failed')
    }
  }

  async function handleProfileSave(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      await updateProfile({ full_name: fullName, display_name: displayName })
      setSaved(true)
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Could not save changes.')
    } finally {
      setSaving(false)
    }
  }

  async function handleSignOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  if (!user) return null

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Settings" description="Profile, appearance, connection, and account." />

      <Card className="p-5 space-y-4">
        <SectionLabel>Profile</SectionLabel>
        <div className="flex items-center gap-3">
          <Avatar name={greetingName(user)} avatarUrl={user.avatar_url} size={48} />
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)]">{greetingName(user)}</p>
            <p className="text-xs text-[var(--text-tertiary)]">{user.email}</p>
          </div>
        </div>

        <form onSubmit={handleProfileSave} className="space-y-3">
          <div className="space-y-1">
            <label htmlFor="settings-display-name" className="text-xs text-[var(--text-tertiary)]">
              Display name
            </label>
            <input
              id="settings-display-name"
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="settings-full-name" className="text-xs text-[var(--text-tertiary)]">
              Full name
            </label>
            <input
              id="settings-full-name"
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <span className="text-xs text-[var(--text-tertiary)]">Email</span>
            <p className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text-secondary)]">
              {user.email}
            </p>
          </div>
          <div className="space-y-1">
            <span className="text-xs text-[var(--text-tertiary)]">Authentication method</span>
            <p className="text-sm text-[var(--text-secondary)]">
              {user.auth_provider === 'GOOGLE' ? 'Google' : 'Email & password'}
            </p>
          </div>

          {saveError && <p className="text-sm text-[var(--negative)]">{saveError}</p>}
          {saved && <p className="text-sm text-[var(--positive)]">Saved.</p>}

          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[var(--accent-strong)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:active:scale-100"
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </Card>

      <Card className="p-5 space-y-3">
        <SectionLabel>Appearance</SectionLabel>
        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--text-secondary)]">Theme</span>
          <ThemeToggle />
        </div>
      </Card>

      <Card className="p-5 space-y-3">
        <SectionLabel>API / Application</SectionLabel>
        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--text-secondary)]">Backend base URL</span>
          <span className="font-mono-tabular text-[var(--text-primary)]">{API_BASE_URL}</span>
        </div>
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={handleCheckConnection}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--surface-2)]"
          >
            Check connection
          </button>
          {checkResult === 'checking' && <span className="text-xs text-[var(--text-tertiary)]">Checking…</span>}
          {checkResult === 'ok' && (
            <span className="text-xs text-[var(--positive)]">
              Connected, {health?.service} v{health?.version}
            </span>
          )}
          {checkResult === 'failed' && <span className="text-xs text-[var(--negative)]">Could not reach the API.</span>}
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--text-secondary)]">Product</span>
          <span className="text-[var(--text-primary)]">TradeLens AI</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-[var(--text-secondary)]">Frontend version</span>
          <span className="font-mono-tabular text-[var(--text-primary)]">0.1.0</span>
        </div>
      </Card>

      <Card className="p-5 space-y-3">
        <SectionLabel>Account</SectionLabel>
        {user.auth_provider === 'LOCAL' ? (
          <p className="text-xs text-[var(--text-tertiary)]">
            Password change is not yet available. This section is reserved for that capability.
          </p>
        ) : (
          <p className="text-xs text-[var(--text-tertiary)]">Signed in with Google. No TradeLens password is used.</p>
        )}
        <button
          type="button"
          onClick={handleSignOut}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium text-[var(--negative)] hover:bg-[var(--negative-soft)]"
        >
          Sign out
        </button>
      </Card>
    </div>
  )
}
