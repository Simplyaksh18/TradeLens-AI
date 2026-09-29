import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ChevronDown, LogOut, Settings as SettingsIcon } from 'lucide-react'
import { useAuth } from '../../auth/useAuth'
import { Avatar } from './Avatar'
import { greetingName } from '../../utils/greeting'

export function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  if (!user) return null
  const name = greetingName(user)

  async function handleSignOut() {
    setOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Open user menu for ${name}`}
        className="flex items-center gap-1.5 rounded-md p-1 hover:bg-[var(--surface-2)]"
      >
        <Avatar name={name} avatarUrl={user.avatar_url} />
        <ChevronDown size={14} className="text-[var(--text-tertiary)]" aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-2 w-56 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] p-1.5 shadow-[var(--shadow-2)]"
        >
          <div className="px-2.5 py-2">
            <p className="text-sm font-medium text-[var(--text-primary)]">{name}</p>
            <p className="text-xs text-[var(--text-tertiary)]">{user.email}</p>
          </div>
          <div className="my-1 border-t border-[var(--border)]" />
          <Link
            to="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded px-2.5 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
          >
            <SettingsIcon size={14} aria-hidden="true" />
            Profile &amp; Settings
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={handleSignOut}
            className="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-left text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
          >
            <LogOut size={14} aria-hidden="true" />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
