import { createContext } from 'react'

// Phase 1G: "system" was removed from user-facing choices (see CLAUDE.md) —
// only an explicit LIGHT/DARK toggle remains. ThemeProvider still migrates
// any previously-stored "system" preference safely (see readStoredPreference).
export type ThemePreference = 'light' | 'dark'

export interface ThemeContextValue {
  preference: ThemePreference
  setPreference: (preference: ThemePreference) => void
  toggle: () => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
