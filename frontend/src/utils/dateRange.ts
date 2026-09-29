export type RangeShortcut = '1M' | '3M' | '6M' | '1Y' | '3Y' | '5Y'

export const RANGE_SHORTCUTS: RangeShortcut[] = ['1M', '3M', '6M', '1Y', '3Y', '5Y']

// Mirrors backend/app/api/dependencies.py's MAX_HISTORY_SPAN_DAYS (365 * 5).
// A calendar-correct "5 years ago" can legitimately span 1826 days instead
// of 1825 whenever the window crosses a leap day — discovered by manually
// exercising the 5Y shortcut, which otherwise fails against the backend's
// hard day-count cap despite being calendar-accurate.
const MAX_HISTORY_SPAN_DAYS = 365 * 5
const MS_PER_DAY = 24 * 60 * 60 * 1000

/** Formats a Date as YYYY-MM-DD using LOCAL date components (never UTC —
 * avoids off-by-one-day bugs for users west of UTC). */
export function toIsoDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Computes [start, end] for a shortcut using calendar month/year
 * arithmetic (Date.setMonth/setFullYear), not a naive `days * 365`
 * multiplication — that would silently drift across leap years and
 * variable month lengths. `end` defaults to today. */
export function computeRangeForShortcut(shortcut: RangeShortcut, today: Date = new Date()): { start: string; end: string } {
  const end = new Date(today)
  const start = new Date(today)

  switch (shortcut) {
    case '1M':
      start.setMonth(start.getMonth() - 1)
      break
    case '3M':
      start.setMonth(start.getMonth() - 3)
      break
    case '6M':
      start.setMonth(start.getMonth() - 6)
      break
    case '1Y':
      start.setFullYear(start.getFullYear() - 1)
      break
    case '3Y':
      start.setFullYear(start.getFullYear() - 3)
      break
    case '5Y':
      start.setFullYear(start.getFullYear() - 5)
      break
  }

  // Calendar arithmetic is correct but can occasionally exceed the
  // backend's fixed day-count cap (see MAX_HISTORY_SPAN_DAYS above); nudge
  // the start date forward by the overage rather than silently sending a
  // request the backend will reject.
  const spanDays = Math.round((end.getTime() - start.getTime()) / MS_PER_DAY)
  if (spanDays > MAX_HISTORY_SPAN_DAYS) {
    start.setDate(start.getDate() + (spanDays - MAX_HISTORY_SPAN_DAYS))
  }

  return { start: toIsoDate(start), end: toIsoDate(end) }
}
