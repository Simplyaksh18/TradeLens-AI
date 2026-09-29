import type { OHLCVBar } from '../../api/types'
import { formatDate, formatInteger, formatNumber } from '../../utils/format'

export function OHLCVTable({ bars }: { bars: OHLCVBar[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)]">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-3 py-2 font-medium">Date</th>
            <th className="px-3 py-2 font-medium text-right">Open</th>
            <th className="px-3 py-2 font-medium text-right">High</th>
            <th className="px-3 py-2 font-medium text-right">Low</th>
            <th className="px-3 py-2 font-medium text-right">Close</th>
            <th className="px-3 py-2 font-medium text-right">Adj Close</th>
            <th className="px-3 py-2 font-medium text-right">Volume</th>
          </tr>
        </thead>
        <tbody className="font-mono-tabular">
          {bars.map((bar) => (
            <tr key={bar.date} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)]">
              <td className="px-3 py-1.5 whitespace-nowrap">{formatDate(bar.date)}</td>
              <td className="px-3 py-1.5 text-right">{formatNumber(bar.open)}</td>
              <td className="px-3 py-1.5 text-right">{formatNumber(bar.high)}</td>
              <td className="px-3 py-1.5 text-right">{formatNumber(bar.low)}</td>
              <td className="px-3 py-1.5 text-right">{formatNumber(bar.close)}</td>
              <td className="px-3 py-1.5 text-right">{formatNumber(bar.adj_close)}</td>
              <td className="px-3 py-1.5 text-right">{formatInteger(bar.volume)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
