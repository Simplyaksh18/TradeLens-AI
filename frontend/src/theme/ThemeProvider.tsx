import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ThemeContext, type ThemePreference } from './ThemeContext'

const STORAGE_KEY = 'tradelens.theme'

function systemPrefersDark(): boolean {
  try {
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  } catch {
    return false
  }
}

/** Reads the stored preference. Phase 1G removed "system" as a user-facing
 * choice; a previously-stored "system" value (or anything unrecognized) is
 * migrated to a concrete LIGHT/DARK default derived from the OS preference
 * at the moment of migration, rather than crashing or silently ignoring the
 * old preference. */
function readStoredPreference(): ThemePreference {
  let stored: string | null = null
  try {
    stored = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    // localStorage unavailable (e.g. private browsing) — fall back below
  }
  if (stored === 'light' || stored === 'dark') return stored
  return systemPrefersDark() ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => readStoredPreference())

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', preference)
    try {
      window.localStorage.setItem(STORAGE_KEY, preference)
    } catch {
      // ignore persistence failures
    }
  }, [preference])

  const setPreference = useCallback((next: ThemePreference) => setPreferenceState(next), [])
  const toggle = useCallback(() => setPreferenceState((prev) => (prev === 'light' ? 'dark' : 'light')), [])

  const value = useMemo(() => ({ preference, setPreference, toggle }), [preference, setPreference, toggle])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
