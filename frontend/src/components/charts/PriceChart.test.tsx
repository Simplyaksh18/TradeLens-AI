import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, render } from '@testing-library/react'
import { ThemeProvider } from '../../theme/ThemeProvider'
import { useTheme } from '../../theme/useTheme'
import { PriceChart } from './PriceChart'
import type { OHLCVBar, StrategyEvaluation } from '../../api/types'

const seriesStub = () => ({
  setData: vi.fn(),
  applyOptions: vi.fn(),
  priceScale: () => ({ applyOptions: vi.fn() }),
  createPriceLine: vi.fn(() => ({ applyOptions: vi.fn() })),
})

const chartStub = {
  addSeries: vi.fn(),
  applyOptions: vi.fn(),
  remove: vi.fn(),
  subscribeCrosshairMove: vi.fn(),
  unsubscribeCrosshairMove: vi.fn(),
  timeScale: () => ({ fitContent: vi.fn(), borderColor: undefined }),
}

const createChartMock = vi.fn((..._args: unknown[]) => chartStub)
const setMarkersMock = vi.fn()
const createSeriesMarkersMock = vi.fn((..._args: unknown[]) => ({ setMarkers: setMarkersMock }))

vi.mock('lightweight-charts', () => ({
  createChart: (...args: unknown[]) => createChartMock(...args),
  createSeriesMarkers: (...args: unknown[]) => createSeriesMarkersMock(...args),
  CandlestickSeries: 'CandlestickSeries',
  LineSeries: 'LineSeries',
  HistogramSeries: 'HistogramSeries',
}))

function bar(date: string, close: number): OHLCVBar {
  return { date, open: close - 1, high: close + 1, low: close - 2, close, adj_close: close, volume: 1000 }
}

function evaluation(date: string, decision: StrategyEvaluation['decision']): StrategyEvaluation {
  return {
    date,
    strategy_id: 'trend_momentum_v1',
    strategy_name: 'Trend + Momentum v1',
    decision,
    conditions: [],
    missing_inputs: [],
  }
}

function ThemeToggleProbe({ onReady }: { onReady: (toggle: () => void) => void }) {
  const { toggle } = useTheme()
  onReady(toggle)
  return null
}

describe('PriceChart', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    chartStub.addSeries.mockImplementation(() => seriesStub())
  })

  it('creates the chart exactly once, even across a theme change (no recreation)', () => {
    let toggle: (() => void) | null = null
    const bars = [bar('2026-01-01', 100), bar('2026-01-02', 101)]
    const evaluations = [evaluation('2026-01-01', 'NO_SIGNAL'), evaluation('2026-01-02', 'BUY')]

    const { rerender } = render(
      <ThemeProvider>
        <ThemeToggleProbe onReady={(t) => (toggle = t)} />
        <PriceChart bars={bars} buySignals={evaluations} />
      </ThemeProvider>,
    )

    expect(createChartMock).toHaveBeenCalledTimes(1)

    act(() => toggle!())
    rerender(
      <ThemeProvider>
        <ThemeToggleProbe onReady={(t) => (toggle = t)} />
        <PriceChart bars={bars} buySignals={evaluations} />
      </ThemeProvider>,
    )

    // Still exactly one chart instance -- theme change restyles, it does
    // not tear down and recreate (that was the root cause of the marker/SMA
    // disappearing-on-theme-switch bug).
    expect(createChartMock).toHaveBeenCalledTimes(1)
    expect(chartStub.remove).not.toHaveBeenCalled()
  })

  it('reapplies markers after a theme change so they are never lost', () => {
    const bars = Array.from({ length: 5 }, (_, i) => bar(`2026-01-0${i + 1}`, 100 + i))
    const evaluations = bars.map((b, i) => evaluation(b.date, i >= 1 && i <= 3 ? 'BUY' : 'NO_SIGNAL'))

    let toggle: (() => void) | null = null
    render(
      <ThemeProvider>
        <ThemeToggleProbe onReady={(t) => (toggle = t)} />
        <PriceChart bars={bars} buySignals={evaluations} />
      </ThemeProvider>,
    )

    const callsBeforeToggle = setMarkersMock.mock.calls.length
    expect(callsBeforeToggle).toBeGreaterThan(0)

    act(() => toggle!())

    expect(setMarkersMock.mock.calls.length).toBeGreaterThan(callsBeforeToggle)
  })

  it('renders exactly one transition marker for a multi-day BUY run, not one per day', () => {
    const bars = Array.from({ length: 5 }, (_, i) => bar(`2026-01-0${i + 1}`, 100 + i))
    const evaluations = bars.map((b, i) => evaluation(b.date, i >= 1 && i <= 3 ? 'BUY' : 'NO_SIGNAL'))

    render(
      <ThemeProvider>
        <PriceChart bars={bars} buySignals={evaluations} />
      </ThemeProvider>,
    )

    const lastCallMarkers = setMarkersMock.mock.calls.at(-1)?.[0]
    expect(lastCallMarkers).toHaveLength(1)
    expect(lastCallMarkers[0].text).toBe('BUY ×3')
  })

  it('marker generation depends on actual evaluations, not chart data (no markers with no BUY evaluations)', () => {
    const bars = [bar('2026-01-01', 100), bar('2026-01-02', 101)]
    const evaluations = [evaluation('2026-01-01', 'NO_SIGNAL'), evaluation('2026-01-02', 'INSUFFICIENT_DATA')]

    render(
      <ThemeProvider>
        <PriceChart bars={bars} buySignals={evaluations} />
      </ThemeProvider>,
    )

    const lastCallMarkers = setMarkersMock.mock.calls.at(-1)?.[0]
    expect(lastCallMarkers).toEqual([])
  })

  it('displays the legend with the latest bar values when nothing is hovered', () => {
    const bars = [bar('2026-01-01', 100), bar('2026-01-02', 105)]
    const { getByTestId } = render(
      <ThemeProvider>
        <PriceChart bars={bars} />
      </ThemeProvider>,
    )
    const legend = getByTestId('chart-legend')
    expect(legend.textContent).toContain('105.00') // latest close
  })
})
