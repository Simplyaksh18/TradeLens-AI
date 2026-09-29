import type { FailureContextAnalysis } from '../../api/types'
import { Card, SectionLabel } from '../ui/Card'
import { ComparisonTable, type ComparisonRow } from '../tables/ComparisonTable'
import { formatInteger, formatNumber, formatPercent } from '../../utils/format'

function pct(value: number | null): string {
  return value === null ? 'Not available' : formatPercent(value, { signed: true })
}

function num(value: number | null): string {
  return value === null ? 'Not available' : formatNumber(value)
}

/** Phase 4C: signal-time (point-in-time) context comparison, rendered
 * verbatim from the backend `context_analysis` -- no RSI/volatility/
 * regime/trend-distance is (re)computed here, and no derived difference
 * (e.g. "FAILED RSI - NON_FAILED RSI") is added since the backend does
 * not supply one (see CLAUDE.md Phase 4F). */
export function ContextComparison({ context }: { context: FailureContextAnalysis }) {
  const { failed, non_failed: nonFailed } = context

  const rows: ComparisonRow[] = [
    { label: 'Signals', failed: formatInteger(failed.count), nonFailed: formatInteger(nonFailed.count) },
    { label: 'Average RSI14', failed: num(failed.average_rsi14), nonFailed: num(nonFailed.average_rsi14) },
    { label: 'Median RSI14', failed: num(failed.median_rsi14), nonFailed: num(nonFailed.median_rsi14) },
    {
      label: 'Volatility Available / Unavailable',
      failed: `${formatInteger(failed.volatility_available_count)} / ${formatInteger(failed.volatility_unavailable_count)}`,
      nonFailed: `${formatInteger(nonFailed.volatility_available_count)} / ${formatInteger(nonFailed.volatility_unavailable_count)}`,
    },
    {
      label: 'Average 20-Bar Volatility',
      failed: pct(failed.average_annualized_realized_volatility_20),
      nonFailed: pct(nonFailed.average_annualized_realized_volatility_20),
    },
    {
      label: 'Median 20-Bar Volatility',
      failed: pct(failed.median_annualized_realized_volatility_20),
      nonFailed: pct(nonFailed.median_annualized_realized_volatility_20),
    },
    {
      label: 'Average Close vs SMA20',
      failed: pct(failed.average_close_above_sma20_fraction),
      nonFailed: pct(nonFailed.average_close_above_sma20_fraction),
    },
    {
      label: 'Median Close vs SMA20',
      failed: pct(failed.median_close_above_sma20_fraction),
      nonFailed: pct(nonFailed.median_close_above_sma20_fraction),
    },
    {
      label: 'Average SMA20 vs SMA50',
      failed: pct(failed.average_sma20_above_sma50_fraction),
      nonFailed: pct(nonFailed.average_sma20_above_sma50_fraction),
    },
    {
      label: 'Median SMA20 vs SMA50',
      failed: pct(failed.median_sma20_above_sma50_fraction),
      nonFailed: pct(nonFailed.median_sma20_above_sma50_fraction),
    },
    { label: 'Bullish Trend Count', failed: formatInteger(failed.bullish_trend_count), nonFailed: formatInteger(nonFailed.bullish_trend_count) },
    { label: 'Bearish Trend Count', failed: formatInteger(failed.bearish_trend_count), nonFailed: formatInteger(nonFailed.bearish_trend_count) },
    { label: 'Transitional Count', failed: formatInteger(failed.transitional_count), nonFailed: formatInteger(nonFailed.transitional_count) },
    {
      label: 'Insufficient Data Count',
      failed: formatInteger(failed.insufficient_data_count),
      nonFailed: formatInteger(nonFailed.insufficient_data_count),
    },
  ]

  return (
    <Card className="p-4">
      <SectionLabel>Signal-Time Context Comparison</SectionLabel>
      <p className="mt-1 text-xs text-[var(--text-tertiary)]">Values available when each historical signal fired.</p>
      <div className="mt-3">
        <ComparisonTable rows={rows} />
      </div>

      {failed.count === 0 && (
        <p className="mt-2 text-xs text-[var(--text-tertiary)]">No failed signals were present in this research window.</p>
      )}
      {nonFailed.count === 0 && (
        <p className="mt-2 text-xs text-[var(--text-tertiary)]">No non-failed signals were present in this research window.</p>
      )}
    </Card>
  )
}
