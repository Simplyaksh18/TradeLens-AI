import { describe, expect, it } from 'vitest'
import { initialsFor } from './initials'

describe('initialsFor', () => {
  it('takes first+last initials for a two-word name', () => {
    expect(initialsFor('Akshi Kumar')).toBe('AK')
  })

  it('takes a single initial for a one-word name', () => {
    expect(initialsFor('Akshi')).toBe('A')
  })

  it('uses first and last word for a three-word name', () => {
    expect(initialsFor('Akshi Rani Kumar')).toBe('AK')
  })

  it('handles empty input safely', () => {
    expect(initialsFor('')).toBe('?')
  })
})
