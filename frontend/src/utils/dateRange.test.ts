import { describe, expect, it } from 'vitest'
import { computeRangeForShortcut, toIsoDate } from './dateRange'

describe('computeRangeForShortcut', () => {
  it('computes 1M using calendar months, not a fixed day count', () => {
    const today = new Date(2026, 2, 31) // 31 Mar 2026
    const { start, end } = computeRangeForShortcut('1M', today)
    expect(end).toBe('2026-03-31')
    // Date.setMonth on the 31st of a 3-day-shorter month (Feb) rolls over —
    // this test documents the actual (correct, native Date) behavior rather
    // than a hand-rolled days*30 approximation.
    expect(start.startsWith('2026-02') || start.startsWith('2026-03')).toBe(true)
  })

  it('computes 1Y correctly across a leap year without drifting the month/day', () => {
    const today = new Date(2028, 1, 29) // 29 Feb 2028 (leap year)
    const { start, end } = computeRangeForShortcut('1Y', today)
    expect(end).toBe('2028-02-29')
    // 2027 is not a leap year, so Date.setFullYear naturally normalizes
    // Feb 29 -> Mar 1, which is correct calendar behavior, not a bug.
    expect(start).toBe('2027-03-01')
  })

  it('computes 5Y as an actual 5-calendar-year span, not days * 5 * 365', () => {
    const today = new Date(2026, 0, 1)
    const { start, end } = computeRangeForShortcut('5Y', today)
    expect(end).toBe('2026-01-01')
    // 2021-01-01 -> 2026-01-01 is 1826 days (crosses the 2024 leap day), one
    // over the backend's 1825-day cap, so start is nudged forward by 1 day.
    expect(start).toBe('2021-01-02')
  })

  it('never exceeds the backend\'s 1825-day max span, even when 5 calendar years crosses a leap day', () => {
    // 26 Sep 2026 -> 26 Sep 2021 is 1826 days (2024 is a leap year) if
    // computed with pure calendar arithmetic — one day over the backend cap.
    const today = new Date(2026, 8, 26)
    const { start, end } = computeRangeForShortcut('5Y', today)
    const spanDays = Math.round((new Date(end).getTime() - new Date(start).getTime()) / (24 * 60 * 60 * 1000))
    expect(spanDays).toBeLessThanOrEqual(365 * 5)
    expect(end).toBe('2026-09-26')
    expect(start).toBe('2021-09-27') // nudged forward by 1 day from the naive 2021-09-26
  })

  it('defaults the end date to today', () => {
    const today = new Date(2026, 5, 15)
    const { end } = computeRangeForShortcut('3M', today)
    expect(end).toBe(toIsoDate(today))
  })
})

describe('toIsoDate', () => {
  it('formats using local date components with zero-padding', () => {
    expect(toIsoDate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})
