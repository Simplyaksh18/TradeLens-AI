import { NavLink } from 'react-router-dom'
import { NAV_GROUPS } from './navigation'

interface SidebarProps {
  onNavigate?: () => void
}

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <nav className="flex h-full w-64 flex-col gap-6 overflow-y-auto border-r border-[var(--border)] bg-[var(--surface-1)] px-4 py-5" aria-label="Primary">
      <div className="px-2">
        <span className="text-base font-semibold tracking-tight">TradeLens</span>
        <span className="ml-1 text-base font-semibold tracking-tight text-[var(--accent)]">AI</span>
      </div>

      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="space-y-1">
          <div className="px-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
            {group.label}
          </div>
          {group.items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md border-l-2 px-2.5 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]'
                }`
              }
            >
              <item.icon size={16} aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )
}
