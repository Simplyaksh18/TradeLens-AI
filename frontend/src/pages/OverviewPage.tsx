import { useState } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import { ResearchToolbar, type ResearchSelection } from '../components/research/ResearchToolbar'
import { Card, SectionLabel } from '../components/ui/Card'
import { ApiErrorState, LoadingSkeleton, NothingSelectedState } from '../components/ui/States'
import { DecisionChip, ConditionOutcome } from '../components/ui/DecisionChip'
import { PriceChart } from '../components/charts/PriceChart'
import { RsiChart } from '../components/charts/RsiChart'
import { useMarketData } from '../hooks/useMarketData'
import { useIndicators } from '../hooks/useIndicators'
import { useStrategyEvaluations } from '../hooks/useStrategyEvaluations'
import { formatDate, formatInteger, formatNumber } from '../utils/format'

export default function OverviewPage() {
  const [selection, setSelection] = useState<ResearchSelection | null>(null)
  const symbol = selection?.instrument.symbol ?? null
  const start = selection?.start ?? ''
  const end = selection?.end ?? ''

  const marketData = useMarketData(symbol, start, end)
  const indicators = useIndicators(symbol, start, end)
  const strategy = useStrategyEvaluations(symbol, start, end)

  const latestBar = marketData.data?.bars.at(-1) ?? null
  const latestIndicatorRow = indicators.data?.rows.at(-1) ?? null
  const latestEvaluation = strategy.data?.evaluations.at(-1) ?? null

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Research market structure. Test deterministic strategy logic. Understand why a signal fired."
      />

      <ResearchToolbar onLoad={setSelection} />

      {!selection && <NothingSelectedState message="Select an instrument and date range, then Load Data to begin." />}

      {selection && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Card className="p-4 xl:col-span-1">
            <SectionLabel>Instrument</SectionLabel>
            <div className="mt-2 space-y-0.5">
              <div className="text-lg font-semibold font-mono-tabular">{selection.instrument.symbol}</div>
              <div className="text-sm text-[var(--text-secondary)]">{selection.instrument.name}</div>
              <div className="text-xs text-[var(--text-tertiary)]">
                {selection.instrument.exchange} · {selection.instrument.provider_symbol}
              </div>
            </div>
          </Card>

          <Card className="p-4 xl:col-span-1">
            <SectionLabel>Latest Market Snapshot</SectionLabel>
            {marketData.loading && <LoadingSkeleton lines={2} />}
            {marketData.error && <ApiErrorState error={marketData.error} />}
            {latestBar && (
              <dl className="mt-2 grid grid-cols-3 gap-x-3 gap-y-1 text-sm font-mono-tabular">
                <dt className="text-[var(--text-tertiary)] text-xs col-span-3">{formatDate(latestBar.date)}</dt>
                <dt className="text-[var(--text-tertiary)] text-xs">Open</dt>
                <dd className="col-span-2 text-right">{formatNumber(latestBar.open)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">High</dt>
                <dd className="col-span-2 text-right">{formatNumber(latestBar.high)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">Low</dt>
                <dd className="col-span-2 text-right">{formatNumber(latestBar.low)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">Close</dt>
                <dd className="col-span-2 text-right">{formatNumber(latestBar.close)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">Volume</dt>
                <dd className="col-span-2 text-right">{formatInteger(latestBar.volume)}</dd>
              </dl>
            )}
          </Card>

          <Card className="p-4 xl:col-span-1">
            <SectionLabel>Latest Indicator State</SectionLabel>
            {indicators.loading && <LoadingSkeleton lines={2} />}
            {indicators.error && <ApiErrorState error={indicators.error} />}
            {latestIndicatorRow && (
              <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-sm font-mono-tabular">
                <dt className="text-[var(--text-tertiary)] text-xs">SMA 20</dt>
                <dd className="text-right">{formatNumber(latestIndicatorRow.sma20)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">SMA 50</dt>
                <dd className="text-right">{formatNumber(latestIndicatorRow.sma50)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">RSI 14</dt>
                <dd className="text-right">{formatNumber(latestIndicatorRow.rsi14)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">Avg Volume</dt>
                <dd className="text-right">{formatInteger(latestIndicatorRow.average_volume)}</dd>
                <dt className="text-[var(--text-tertiary)] text-xs">Volume Ratio</dt>
                <dd className="text-right">{formatNumber(latestIndicatorRow.volume_ratio)}</dd>
              </dl>
            )}
          </Card>

          <Card className="p-4 xl:col-span-3">
            <div className="flex items-center justify-between">
              <SectionLabel>Trend + Momentum V1: Current State</SectionLabel>
              {latestEvaluation && <DecisionChip decision={latestEvaluation.decision} />}
            </div>
            {strategy.loading && <LoadingSkeleton lines={2} />}
            {strategy.error && <ApiErrorState error={strategy.error} />}
            {latestEvaluation && (
              <div className="mt-2 space-y-1.5">
                <p className="text-xs text-[var(--text-tertiary)]">As of {formatDate(latestEvaluation.date)}</p>
                {latestEvaluation.decision === 'INSUFFICIENT_DATA' ? (
                  <p className="text-sm text-[var(--warning)]">
                    Insufficient history to evaluate this strategy. Missing: {latestEvaluation.missing_inputs.join(' · ')}
                  </p>
                ) : (
                  <ul className="space-y-1 text-sm">
                    {latestEvaluation.conditions.map((c) => (
                      <li key={c.condition_id} className="flex items-center justify-between gap-3">
                        <span className="text-[var(--text-secondary)]">{c.description}</span>
                        <ConditionOutcome passed={c.passed} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </Card>

          <Card className="p-4 xl:col-span-3">
            <SectionLabel>Price Chart</SectionLabel>
            {marketData.data && (
              <div className="mt-2 space-y-3">
                <PriceChart
                  bars={marketData.data.bars}
                  indicatorRows={indicators.data?.rows ?? []}
                  buySignals={strategy.data?.evaluations ?? []}
                />
                <RsiChart rows={indicators.data?.rows ?? []} />
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
