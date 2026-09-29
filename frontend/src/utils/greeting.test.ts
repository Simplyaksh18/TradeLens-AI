import { describe, expect, it } from 'vitest'
import { greetingForHour, greetingName } from './greeting'

describe('greetingForHour', () => {
  it('is "Good morning" at the start of the morning boundary (05:00)', () => {
    expect(greetingForHour(5)).toBe('Good morning')
  })

  it('is "Good morning" just before the afternoon boundary (11:59 -> hour 11)', () => {
    expect(greetingForHour(11)).toBe('Good morning')
  })

  it('is "Good afternoon" at the start of the afternoon boundary (12:00)', () => {
    expect(greetingForHour(12)).toBe('Good afternoon')
  })

  it('is "Good afternoon" just before the evening boundary (16:59 -> hour 16)', () => {
    expect(greetingForHour(16)).toBe('Good afternoon')
  })

  it('is "Good evening" at the start of the evening boundary (17:00)', () => {
    expect(greetingForHour(17)).toBe('Good evening')
  })

  it('is "Good evening" late at night (23:00)', () => {
    expect(greetingForHour(23)).toBe('Good evening')
  })

  it('is "Good evening" in the early hours, just before morning (04:00)', () => {
    expect(greetingForHour(4)).toBe('Good evening')
  })

  it('is "Good evening" at midnight (00:00)', () => {
    expect(greetingForHour(0)).toBe('Good evening')
  })
})

describe('greetingName', () => {
  it('prefers display_name', () => {
    expect(greetingName({ display_name: 'Akshi', full_name: 'Akshi Kumar' })).toBe('Akshi')
  })

  it('falls back to full_name when display_name is empty', () => {
    expect(greetingName({ display_name: '', full_name: 'Akshi Kumar' })).toBe('Akshi Kumar')
  })

  it('falls back to full_name when display_name is only whitespace', () => {
    expect(greetingName({ display_name: '   ', full_name: 'Akshi Kumar' })).toBe('Akshi Kumar')
  })
})
