import { Menu } from 'lucide-react'
import { ThemeToggle } from './ThemeToggle'
import { UserMenu } from './UserMenu'
import { useAuth } from '../../auth/useAuth'
import { currentGreeting, greetingName } from '../../utils/greeting'

interface TopBarProps {
  pageTitle: string
  onMenuClick: () => void
}

export function TopBar({ pageTitle, onMenuClick }: TopBarProps) {
  const { user } = useAuth()

  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--surface-1)] px-4">
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="rounded p-1.5 hover:bg-[var(--surface-2)] lg:hidden"
          aria-label="Open navigation menu"
          onClick={onMenuClick}
        >
          <Menu size={18} aria-hidden="true" />
        </button>
        <span className="text-sm font-medium text-[var(--text-primary)]">{pageTitle}</span>
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <span className="hidden text-sm text-[var(--text-secondary)] md:inline">
            {currentGreeting()}, <span className="font-medium text-[var(--text-primary)]">{greetingName(user)}</span>
          </span>
        )}

        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  )
}
