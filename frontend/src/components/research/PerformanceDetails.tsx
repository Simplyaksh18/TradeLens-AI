import type { PerformanceAnalyticsResponse } from '../../api/types'
import { formatCurrency, formatDate, formatInteger, formatPercent } from '../../utils/format'
import { Card, SectionLabel } from '../ui/Card'

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className="font-mono-tabular text-[var(--text-primary)]">{value}</span>
    </div>
  )
}

/** Only the accepted Phase 2C V1 fields — never annualized volatility,
 * CAGR, Sharpe/Sortino/Calmar, alpha/beta, or VaR/CVaR (all explicitly
 * deferred; see CLAUDE.md Phase 2C). */
export function PerformanceDetails({ analytics }: { analytics: PerformanceAnalyticsResponse }) {
  return (
    <Card className="p-4">
      <SectionLabel>Performance &amp; Risk Details</SectionLabel>
      <div className="mt-2 grid grid-cols-1 gap-x-6 sm:grid-cols-2 divide-y divide-[var(--border)] sm:divide-y-0">
        <div>
          <DetailRow label="Initial Equity" value={formatCurrency(analytics.initial_equity)} />
          <DetailRow label="Ending Equity" value={formatCurrency(analytics.ending_equity)} />
          <DetailRow label="Realized P&L" value={formatCurrency(analytics.realized_pnl)} />
          <DetailRow label="Unrealized P&L" value={formatCurrency(analytics.unrealized_pnl)} />
          <DetailRow label="Peak Equity" value={formatCurrency(analytics.peak_equity)} />
          <DetailRow label="Max DD Peak Date" value={formatDate(analytics.max_drawdown_peak_date)} />
          <DetailRow label="Max DD Trough Date" value={formatDate(analytics.max_drawdown_trough_date)} />
        </div>
        <div>
          <DetailRow label="Winner Count" value={formatInteger(analytics.winner_count)} />
          <DetailRow label="Loser Count" value={formatInteger(analytics.loser_count)} />
          <DetailRow label="Breakeven Count" value={formatInteger(analytics.breakeven_count)} />
          <DetailRow label="Average Trade Return" value={formatPercent(analytics.average_trade_return, { signed: true })} />
          <DetailRow label="Median Trade Return" value={formatPercent(analytics.median_trade_return, { signed: true })} />
          <DetailRow label="Best Trade Return" value={formatPercent(analytics.best_trade_return, { signed: true })} />
          <DetailRow label="Worst Trade Return" value={formatPercent(analytics.worst_trade_return, { signed: true })} />
        </div>
      </div>
    </Card>
  )
}
