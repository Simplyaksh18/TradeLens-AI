import type { PerformanceAnalyticsResponse } from '../../api/types'
import { formatCurrency, formatPercent } from '../../utils/format'

function semanticClass(value: number | null): string {
  if (value === null || value === 0) return 'text-[var(--text-primary)]'
  return value > 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'
}

function SummaryTile({ label, value, valueClassName = 'text-[var(--text-primary)]' }: { label: string; value: string; valueClassName?: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-4 py-3">
      <p className="text-xs text-[var(--text-tertiary)]">{label}</p>
      <p className={`mt-1 text-lg font-semibold font-mono-tabular ${valueClassName}`}>{value}</p>
    </div>
  )
}

/** Renders exactly the accepted Phase 2C `PerformanceAnalyticsResponse`
 * fields, formatted for display only — no metric here is recomputed from
 * trades/equity in React (see CLAUDE.md Phase 2C/2E). */
export function PerformanceSummary({ analytics }: { analytics: PerformanceAnalyticsResponse }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <SummaryTile label="Total Return" value={formatPercent(analytics.total_return, { signed: true })} valueClassName={semanticClass(analytics.total_return)} />
      <SummaryTile label="Total P&L" value={formatCurrency(analytics.total_pnl)} valueClassName={semanticClass(analytics.total_pnl)} />
      <SummaryTile label="Max Drawdown" value={formatPercent(analytics.maximum_drawdown, { signed: true })} valueClassName={semanticClass(analytics.maximum_drawdown)} />
      <SummaryTile label="Win Rate" value={formatPercent(analytics.win_rate)} />
      <SummaryTile label="Closed Trades" value={String(analytics.closed_trade_count)} />
      <SummaryTile label="Exposure" value={formatPercent(analytics.exposure)} />
    </div>
  )
}
