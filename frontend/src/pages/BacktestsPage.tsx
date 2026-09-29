import { useState } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import { BacktestControls, type BacktestSelection } from '../components/research/BacktestControls'
import { PerformanceSummary } from '../components/research/PerformanceSummary'
import { PerformanceDetails } from '../components/research/PerformanceDetails'
import { OpenPositionPanel } from '../components/research/OpenPositionPanel'
import { Card, SectionLabel } from '../components/ui/Card'
import { ApiErrorState, LoadingSkeleton, NothingSelectedState } from '../components/ui/States'
import { Tabs } from '../components/ui/Tabs'
import { SimpleLineChart } from '../components/charts/SimpleLineChart'
import { TradesTable } from '../components/tables/TradesTable'
import { SignalOutcomesTable } from '../components/tables/SignalOutcomesTable'
import { useSignalOutcomes } from '../hooks/useSignalOutcomes'
import { useBacktestResult } from '../hooks/useBacktestResult'
import { usePerformanceAnalytics } from '../hooks/usePerformanceAnalytics'
import { formatCurrency, formatPercent } from '../utils/format'

export default function BacktestsPage() {
  const [selection, setSelection] = useState<BacktestSelection | null>(null)

  const symbol = selection?.instrument.symbol ?? null
  const start = selection?.start ?? ''
  const end = selection?.end ?? ''
  const initialCapital = selection?.initialCapital ?? 100_000

  const outcomes = useSignalOutcomes(symbol, start, end)
  const backtest = useBacktestResult(symbol, start, end, initialCapital)
  const analytics = usePerformanceAnalytics(symbol, start, end, initialCapital)

  const anyLoading = outcomes.loading || backtest.loading || analytics.loading
  const firstError = backtest.error ?? analytics.error ?? outcomes.error
  const ready = !anyLoading && !firstError && Boolean(outcomes.data && backtest.data && analytics.data)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Backtests"
        description="Run the accepted Trend + Momentum v1 research pipeline: historical BUY-signal outcomes, an executable backtest, and performance/risk analytics."
      />

      <BacktestControls onRun={setSelection} />

      {!selection && (
        <NothingSelectedState message="Select an instrument and historical period to evaluate Trend + Momentum v1." />
      )}

      {selection && anyLoading && (
        <Card className="p-6">
          <LoadingSkeleton lines={5} />
        </Card>
      )}

      {selection && !anyLoading && firstError && <ApiErrorState error={firstError} />}

      {selection && ready && outcomes.data && backtest.data && analytics.data && (
        <div className="space-y-4">
          <PerformanceSummary analytics={analytics.data} />

          <Card className="p-4">
            <SectionLabel>Equity Curve</SectionLabel>
            <div className="mt-2">
              <SimpleLineChart
                data={backtest.data.equity_curve.map((p) => ({ date: p.date, value: p.equity }))}
                valueLabel="Equity"
                formatValue={(v) => formatCurrency(v)}
                testId="equity-chart"
                emptyMessage="No equity data for the selected period."
              />
            </div>
          </Card>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <PerformanceDetails analytics={analytics.data} />
            <OpenPositionPanel backtest={backtest.data} analytics={analytics.data} />
          </div>

          <Card className="p-4">
            <Tabs
              items={[
                { id: 'trades', label: 'Trades', content: <TradesTable trades={backtest.data.trades} /> },
                { id: 'outcomes', label: 'Signal Outcomes', content: <SignalOutcomesTable outcomes={outcomes.data.outcomes} /> },
                {
                  id: 'drawdown',
                  label: 'Drawdown',
                  content: (
                    <SimpleLineChart
                      data={analytics.data.drawdown_series.map((p) => ({ date: p.date, value: p.drawdown }))}
                      valueLabel="Drawdown"
                      formatValue={(v) => formatPercent(v, { signed: true })}
                      color="negative"
                      testId="drawdown-chart"
                      emptyMessage="No drawdown data for the selected period."
                    />
                  ),
                },
              ]}
            />
          </Card>
        </div>
      )}
    </div>
  )
}
