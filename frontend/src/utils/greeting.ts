import type { AuthUser } from '../api/types'

/** Boundaries (local browser time), per CLAUDE.md Phase 1G:
 *   05:00–11:59  Good morning
 *   12:00–16:59  Good afternoon
 *   17:00–04:59  Good evening
 */
export function greetingForHour(hour: number): string {
  if (hour >= 5 && hour < 12) return 'Good morning'
  if (hour >= 12 && hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function currentGreeting(now: Date = new Date()): string {
  return greetingForHour(now.getHours())
}

/** display_name is preferred; full_name is the safe fallback. Email is
 * never used as the greeting name. */
export function greetingName(user: Pick<AuthUser, 'display_name' | 'full_name'>): string {
  return user.display_name?.trim() || user.full_name?.trim() || ''
}
