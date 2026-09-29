import type { ExecutedTrade } from '../../api/types'
import { formatCurrency, formatDate, formatInteger, formatNumber, formatPercent } from '../../utils/format'
import { NoDataState } from '../ui/States'

function pnlClass(value: number): string {
  if (value === 0) return 'text-[var(--text-primary)]'
  return value > 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'
}

/** Phase 2B CLOSED trades only — an open position is never inserted here
 * (see OpenPositionPanel for that state). */
export function TradesTable({ trades }: { trades: ExecutedTrade[] }) {
  if (trades.length === 0) {
    return <NoDataState message="No closed trades in this period." />
  }

  return (
    <div className="max-h-[420px] overflow-auto rounded-md border border-[var(--border)]">
      <table className="w-full min-w-[820px] text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-3 py-2 font-medium">Entry Signal</th>
            <th className="px-3 py-2 font-medium">Entry Date</th>
            <th className="px-3 py-2 font-medium">Entry Price</th>
            <th className="px-3 py-2 font-medium">Exit Signal</th>
            <th className="px-3 py-2 font-medium">Exit Date</th>
            <th className="px-3 py-2 font-medium">Exit Price</th>
            <th className="px-3 py-2 font-medium">Quantity</th>
            <th className="px-3 py-2 font-medium">Net P&amp;L</th>
            <th className="px-3 py-2 font-medium">Return</th>
            <th className="px-3 py-2 font-medium">Gross P&amp;L</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade, i) => (
            <tr key={`${trade.entry_date}-${i}`} className="border-b border-[var(--border)] last:border-0">
              <td className="px-3 py-1.5 font-mono-tabular whitespace-nowrap">{formatDate(trade.entry_signal_date)}</td>
              <td className="px-3 py-1.5 font-mono-tabular whitespace-nowrap">{formatDate(trade.entry_date)}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(trade.entry_price)}</td>
              <td className="px-3 py-1.5 font-mono-tabular whitespace-nowrap">{formatDate(trade.exit_signal_date)}</td>
              <td className="px-3 py-1.5 font-mono-tabular whitespace-nowrap">{formatDate(trade.exit_date)}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(trade.exit_price)}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatInteger(trade.quantity)}</td>
              <td className={`px-3 py-1.5 font-mono-tabular font-medium ${pnlClass(trade.net_pnl)}`}>{formatCurrency(trade.net_pnl)}</td>
              <td className={`px-3 py-1.5 font-mono-tabular font-medium ${pnlClass(trade.net_pnl)}`}>
                {formatPercent(trade.gross_return, { signed: true })}
              </td>
              <td className="px-3 py-1.5 font-mono-tabular text-[var(--text-secondary)]">{formatCurrency(trade.gross_pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
