import { useState } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import { ResearchToolbar, type ResearchSelection } from '../components/research/ResearchToolbar'
import { Card, SectionLabel } from '../components/ui/Card'
import { ApiErrorState, LoadingSkeleton, NothingSelectedState, NoDataState } from '../components/ui/States'
import { PriceChart } from '../components/charts/PriceChart'
import { StrategyEvaluationTable } from '../components/tables/StrategyEvaluationTable'
import { EvidenceInspector } from '../components/research/EvidenceInspector'
import { useMarketData } from '../hooks/useMarketData'
import { useIndicators } from '../hooks/useIndicators'
import { useStrategyEvaluations } from '../hooks/useStrategyEvaluations'
import type { StrategyEvaluation } from '../api/types'

export default function StrategyLabPage() {
  const [selection, setSelection] = useState<ResearchSelection | null>(null)
  const [selectedEvaluation, setSelectedEvaluation] = useState<StrategyEvaluation | null>(null)

  const symbol = selection?.instrument.symbol ?? null
  const start = selection?.start ?? ''
  const end = selection?.end ?? ''

  const marketData = useMarketData(symbol, start, end)
  const indicators = useIndicators(symbol, start, end)
  const strategy = useStrategyEvaluations(symbol, start, end)

  const evaluations = strategy.data?.evaluations ?? []

  const defaultEvaluation = [...evaluations].reverse().find((e) => e.decision !== 'INSUFFICIENT_DATA') ?? null
  const activeEvaluation = selectedEvaluation ?? defaultEvaluation

  return (
    <div className="space-y-6">
      <PageHeader
        title="Strategy Lab"
        description="Inspect deterministic trading rules and understand exactly why each historical signal state occurred."
      />

      <ResearchToolbar onLoad={(next) => { setSelection(next); setSelectedEvaluation(null) }} />

      {!selection && <NothingSelectedState message="Select an instrument and date range to evaluate Trend + Momentum v1." />}

      {selection && (
        <>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <SectionLabel>Strategy</SectionLabel>
              <select
                disabled
                className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)]"
                aria-label="Strategy selector (only one strategy currently exists)"
              >
                <option>Trend + Momentum v1</option>
              </select>
            </div>
            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
              <div className="rounded border border-[var(--border)] p-3">
                <p className="text-xs font-medium text-[var(--text-tertiary)] mb-1">BUY when ALL conditions pass</p>
                <ul className="space-y-0.5 font-mono-tabular text-[var(--text-secondary)]">
                  <li>Close &gt; SMA20</li>
                  <li>SMA20 &gt; SMA50</li>
                  <li>40 ≤ RSI14 ≤ 70</li>
                </ul>
              </div>
              <div className="rounded border border-[var(--border)] p-3 text-[var(--text-secondary)]">
                <p>Otherwise → <span className="font-medium text-[var(--text-primary)]">NO_SIGNAL</span></p>
                <p className="mt-1">Missing required indicator data → <span className="font-medium text-[var(--text-primary)]">INSUFFICIENT_DATA</span></p>
                <p className="mt-2 text-xs text-[var(--text-tertiary)]">No SELL logic exists in TradeLens yet.</p>
              </div>
            </div>
          </Card>

          {(marketData.loading || indicators.loading || strategy.loading) && (
            <Card className="p-6">
              <LoadingSkeleton lines={4} />
            </Card>
          )}

          {(marketData.error || indicators.error || strategy.error) && (
            <ApiErrorState error={marketData.error ?? indicators.error ?? strategy.error} />
          )}

          {strategy.data && evaluations.length === 0 && <NoDataState message="No evaluations were returned for this period." />}

          {marketData.data && strategy.data && evaluations.length > 0 && (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              <Card className="p-4 xl:col-span-2">
                <SectionLabel>Price &amp; Signal Timeline</SectionLabel>
                <div className="mt-2">
                  <PriceChart
                    bars={marketData.data.bars}
                    indicatorRows={indicators.data?.rows ?? []}
                    buySignals={evaluations}
                  />
                </div>
              </Card>

              <Card className="p-4 xl:col-span-1">
                <EvidenceInspector evaluation={activeEvaluation} />
              </Card>

              <Card className="p-4 xl:col-span-3">
                <SectionLabel>Historical Evaluations</SectionLabel>
                <div className="mt-2">
                  <StrategyEvaluationTable
                    evaluations={evaluations}
                    selectedDate={activeEvaluation?.date}
                    onSelect={setSelectedEvaluation}
                  />
                </div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}
