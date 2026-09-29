import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../../theme/useTheme'

/** Single compact LIGHT/DARK toggle (Phase 1G removed "System" as a
 * user-facing choice — see CLAUDE.md). Still keyboard-accessible: a real
 * <button> with an aria-label describing the action it performs. */
export function ThemeToggle() {
  const { preference, toggle } = useTheme()
  const isDark = preference === 'dark'

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      className="flex items-center justify-center rounded-md border border-[var(--border)] p-1.5 text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
    >
      {isDark ? <Sun size={15} aria-hidden="true" /> : <Moon size={15} aria-hidden="true" />}
    </button>
  )
}
