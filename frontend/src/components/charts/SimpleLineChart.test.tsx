import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, render } from '@testing-library/react'
import { ThemeProvider } from '../../theme/ThemeProvider'
import { useTheme } from '../../theme/useTheme'
import { SimpleLineChart } from './SimpleLineChart'

const seriesStub = () => ({ setData: vi.fn(), applyOptions: vi.fn() })

const chartStub = {
  addSeries: vi.fn(),
  applyOptions: vi.fn(),
  remove: vi.fn(),
  subscribeCrosshairMove: vi.fn(),
  unsubscribeCrosshairMove: vi.fn(),
  timeScale: () => ({ fitContent: vi.fn(), borderColor: undefined }),
}

const createChartMock = vi.fn((..._args: unknown[]) => chartStub)

vi.mock('lightweight-charts', () => ({
  createChart: (...args: unknown[]) => createChartMock(...args),
  LineSeries: 'LineSeries',
}))

function ThemeToggleProbe({ onReady }: { onReady: (toggle: () => void) => void }) {
  const { toggle } = useTheme()
  onReady(toggle)
  return null
}

describe('SimpleLineChart', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    chartStub.addSeries.mockImplementation(() => seriesStub())
  })

  it('creates the chart exactly once, even across a theme change', () => {
    let toggle: (() => void) | null = null
    const data = [{ date: '2026-01-01', value: 1000 }, { date: '2026-01-02', value: 1010 }]

    const { rerender } = render(
      <ThemeProvider>
        <ThemeToggleProbe onReady={(t) => (toggle = t)} />
        <SimpleLineChart data={data} valueLabel="Equity" formatValue={(v) => String(v)} />
      </ThemeProvider>,
    )

    expect(createChartMock).toHaveBeenCalledTimes(1)

    act(() => toggle!())
    rerender(
      <ThemeProvider>
        <ThemeToggleProbe onReady={(t) => (toggle = t)} />
        <SimpleLineChart data={data} valueLabel="Equity" formatValue={(v) => String(v)} />
      </ThemeProvider>,
    )

    expect(createChartMock).toHaveBeenCalledTimes(1)
    expect(chartStub.remove).not.toHaveBeenCalled()
  })

  it('sets series data from the given points, without recomputing values', () => {
    const data = [{ date: '2026-01-01', value: 1000 }, { date: '2026-01-02', value: 1234.5 }]
    let series: ReturnType<typeof seriesStub> | null = null
    chartStub.addSeries.mockImplementation(() => {
      series = seriesStub()
      return series
    })

    render(
      <ThemeProvider>
        <SimpleLineChart data={data} valueLabel="Equity" formatValue={(v) => String(v)} />
      </ThemeProvider>,
    )

    expect(series!.setData).toHaveBeenCalledWith([
      { time: expect.any(Number), value: 1000 },
      { time: expect.any(Number), value: 1234.5 },
    ])
  })

  it('shows the legend with the latest point when nothing is hovered', () => {
    const data = [{ date: '2026-01-01', value: 1000 }, { date: '2026-01-02', value: 1234.5 }]
    const { getByTestId } = render(
      <ThemeProvider>
        <SimpleLineChart data={data} valueLabel="Equity" formatValue={(v) => `₹${v}`} testId="my-chart" />
      </ThemeProvider>,
    )
    const legend = getByTestId('my-chart-legend')
    expect(legend.textContent).toContain('₹1234.5')
  })

  it('renders an explicit empty state instead of an empty chart canvas', () => {
    const { getByText, queryByTestId } = render(
      <ThemeProvider>
        <SimpleLineChart data={[]} valueLabel="Equity" formatValue={(v) => String(v)} emptyMessage="Nothing here." testId="my-chart" />
      </ThemeProvider>,
    )
    expect(getByText('Nothing here.')).toBeInTheDocument()
    expect(queryByTestId('my-chart')).not.toBeInTheDocument()
  })
})
