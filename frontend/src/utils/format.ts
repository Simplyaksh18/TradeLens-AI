/** Formats a numeric value with fixed decimals, or a stable placeholder
 * when the value is null/undefined. Never renders null as 0. */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-IN')
}

export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** Presentation only: multiplies a decimal fraction by 100 for display —
 * never mutates or feeds the underlying value back into any calculation.
 * `signed`: prefix an explicit "+" for positive values (used for returns/
 * P&L-shaped metrics, e.g. total_return); omit for plain rates that are
 * never "negative-implying-loss" by convention (win_rate, exposure). */
export function formatPercent(value: number | null | undefined, options: { signed?: boolean; decimals?: number } = {}): string {
  if (value === null || value === undefined) return '—'
  const { signed = false, decimals = 2 } = options
  const percent = value * 100
  const sign = signed && percent > 0 ? '+' : ''
  return `${sign}${percent.toFixed(decimals)}%`
}

/** INR currency formatting for P&L/equity figures. Presentation only. */
export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })
}
