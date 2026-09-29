import { describe, expect, it } from 'vitest'
import { formatNumber, formatInteger, formatPercent, formatCurrency } from './format'

describe('formatNumber', () => {
  it('never renders null as 0', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(null)).not.toBe('0')
    expect(formatNumber(null)).not.toBe('0.00')
  })

  it('never renders undefined as 0', () => {
    expect(formatNumber(undefined)).toBe('—')
  })

  it('renders an actual zero value as zero, not as the placeholder', () => {
    expect(formatNumber(0)).not.toBe('—')
    expect(formatNumber(0)).toBe('0.00')
  })

  it('formats a real number with fixed decimals', () => {
    expect(formatNumber(1284.5)).toBe('1,284.50')
  })
})

describe('formatInteger', () => {
  it('never renders null as 0', () => {
    expect(formatInteger(null)).toBe('—')
  })

  it('renders an actual zero volume as zero, not as the placeholder', () => {
    expect(formatInteger(0)).toBe('0')
    expect(formatInteger(0)).not.toBe('—')
  })
})

describe('formatPercent', () => {
  it('never renders null/undefined as 0%', () => {
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(undefined)).toBe('—')
  })

  it('multiplies by 100 for display only', () => {
    expect(formatPercent(0.0213947)).toBe('2.14%')
    expect(formatPercent(-0.05618)).toBe('-5.62%')
  })

  it('renders a real zero rate as 0.00%, not the placeholder', () => {
    expect(formatPercent(0)).toBe('0.00%')
    expect(formatPercent(0)).not.toBe('—')
  })

  it('signed mode prefixes an explicit + for positive values', () => {
    expect(formatPercent(0.0213947, { signed: true })).toBe('+2.14%')
    expect(formatPercent(-0.05618, { signed: true })).toBe('-5.62%')
    expect(formatPercent(0, { signed: true })).toBe('0.00%')
  })

  it('unsigned mode never adds a + prefix (rates like win_rate/exposure)', () => {
    expect(formatPercent(0.8333)).toBe('83.33%')
    expect(formatPercent(0.8333)).not.toMatch(/^\+/)
  })
})

describe('formatCurrency', () => {
  it('never renders null/undefined as 0', () => {
    expect(formatCurrency(null)).toBe('—')
    expect(formatCurrency(undefined)).toBe('—')
  })

  it('renders a real zero amount as zero, not the placeholder', () => {
    expect(formatCurrency(0)).not.toBe('—')
  })

  it('formats using INR currency style', () => {
    expect(formatCurrency(2139.47)).toContain('2,139.47')
  })
})
