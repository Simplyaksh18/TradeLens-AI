import type { OHLCVBar } from '../api/types'

const COLUMNS = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'] as const

export function ohlcvToCsv(bars: OHLCVBar[]): string {
  const rows = bars.map((bar) =>
    [bar.date, bar.open, bar.high, bar.low, bar.close, bar.adj_close ?? '', bar.volume].join(','),
  )
  return [COLUMNS.join(','), ...rows].join('\n')
}

export function downloadCsv(filename: string, csvContent: string): void {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function buildOhlcvFilename(symbol: string, start: string, end: string, interval: string): string {
  return `${symbol}_${start}_${end}_${interval}.csv`
}
