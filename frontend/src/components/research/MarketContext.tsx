import type { Comparison, MarketRegime, RiskMarketContext } from '../../api/types'
import { formatNumber, formatPercent } from '../../utils/format'
import { Card, SectionLabel } from '../ui/Card'

const REGIME_LABEL: Record<MarketRegime, string> = {
  BULLISH_TREND: 'Bullish Trend',
  BEARISH_TREND: 'Bearish Trend',
  TRANSITIONAL: 'Transitional',
  INSUFFICIENT_DATA: 'Insufficient Data',
}

const REGIME_STYLE: Record<MarketRegime, string> = {
  BULLISH_TREND: 'bg-[var(--positive-soft)] text-[var(--positive)] border-[var(--positive)]/30',
  BEARISH_TREND: 'bg-[var(--negative-soft)] text-[var(--negative)] border-[var(--negative)]/30',
  TRANSITIONAL: 'bg-[var(--neutral-chip)] text-[var(--text-secondary)] border-[var(--border-strong)]',
  INSUFFICIENT_DATA: 'bg-[var(--warning-soft)] text-[var(--warning)] border-[var(--warning)]/30',
}

const COMPARISON_LABEL: Record<Comparison, string> = { ABOVE: 'Above', BELOW: 'Below', EQUAL: 'Equal' }

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className="font-mono-tabular text-[var(--text-primary)]">{value}</span>
    </div>
  )
}

/** Phase 3B risk/regime context, rendered verbatim -- no regime
 * descriptions or predictions are invented beyond the backend's own
 * BULLISH_TREND/BEARISH_TREND/TRANSITIONAL/INSUFFICIENT_DATA enum and its
 * accompanying close/SMA20/SMA50 evidence (see CLAUDE.md Phase 3B). */
export function MarketContext({ context }: { context: RiskMarketContext }) {
  const { regime, regime_evidence: evidence, annualized_realized_volatility_20: volatility } = context

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <SectionLabel>Market Context</SectionLabel>
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${REGIME_STYLE[regime]}`}
          data-regime={regime}
        >
          {REGIME_LABEL[regime]}
        </span>
      </div>

      <div className="mt-3">
        <DetailRow
          label="20-Bar Annualized Realized Volatility"
          value={volatility === null ? 'Not available' : formatPercent(volatility)}
        />
      </div>

      <div className="mt-2 border-t border-[var(--border)] pt-2">
        <DetailRow label="Close" value={formatNumber(evidence.close)} />
        <DetailRow label="SMA20" value={formatNumber(evidence.sma20)} />
        <DetailRow label="SMA50" value={formatNumber(evidence.sma50)} />
        <DetailRow
          label="Close vs SMA20"
          value={evidence.close_vs_sma20 ? COMPARISON_LABEL[evidence.close_vs_sma20] : '—'}
        />
        <DetailRow
          label="SMA20 vs SMA50"
          value={evidence.sma20_vs_sma50 ? COMPARISON_LABEL[evidence.sma20_vs_sma50] : '—'}
        />
      </div>
    </Card>
  )
}
