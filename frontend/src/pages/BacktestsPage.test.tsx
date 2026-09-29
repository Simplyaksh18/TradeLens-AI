import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../theme/ThemeProvider'
import App from '../App'
import BacktestsPage from './BacktestsPage'
import { mockFetchForAuthState, renderWithProviders, TEST_USER } from '../test/authTestUtils'
import * as instrumentsApi from '../api/instruments'
import * as outcomesApi from '../api/outcomes'
import * as backtestsApi from '../api/backtests'
import * as analyticsApi from '../api/analytics'
import { AbortedRequestError, ApiError } from '../api/client'
import type {
  BacktestResultResponse,
  Instrument,
  PerformanceAnalyticsResponse,
  SignalOutcomeSeriesResponse,
} from '../api/types'

// Charts are already covered by SimpleLineChart.test.tsx (mocked
// lightweight-charts, including theme persistence). Real lightweight-charts
// rendering isn't meaningful in jsdom (no canvas) and produces noisy
// unhandled async errors from its own animation-frame draw loop; mock it
// here too so this file can focus on page-level orchestration.
const seriesStub = () => ({ setData: vi.fn(), applyOptions: vi.fn() })
const chartStub = {
  addSeries: vi.fn(() => seriesStub()),
  applyOptions: vi.fn(),
  remove: vi.fn(),
  subscribeCrosshairMove: vi.fn(),
  unsubscribeCrosshairMove: vi.fn(),
  timeScale: () => ({ fitContent: vi.fn() }),
}
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => chartStub),
  LineSeries: 'LineSeries',
}))

const RELIANCE: Instrument = {
  symbol: 'RELIANCE',
  exchange: 'NSE',
  name: 'Reliance Industries Limited',
  provider_symbol: 'RELIANCE.NS',
  instrument_type: 'EQUITY',
  status: 'ACTIVE',
  isin: null,
  series: 'EQ',
}

const OUTCOMES: SignalOutcomeSeriesResponse = {
  provider_symbol: 'RELIANCE.NS',
  interval: '1d',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  outcomes: [
    {
      date: '2024-01-05',
      decision: 'BUY',
      reference_close: 100,
      forward_close_5d: 105,
      forward_return_5d: 0.05,
      forward_close_10d: 110,
      forward_return_10d: 0.1,
      mae_10d: -0.02,
      mfe_10d: 0.12,
      available_forward_bars: 14,
    },
  ],
}

const BACKTEST: BacktestResultResponse = {
  provider_symbol: 'RELIANCE.NS',
  interval: '1d',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  config: { initial_capital: 100000, transaction_cost: 0, slippage: 0 },
  trades: [
    {
      entry_signal_date: '2024-01-05',
      entry_date: '2024-01-08',
      entry_price: 110,
      exit_signal_date: '2024-01-20',
      exit_date: '2024-01-22',
      exit_price: 130,
      quantity: 9,
      gross_pnl: 180,
      gross_return: 0.1818,
      net_pnl: 180,
    },
  ],
  open_position: null,
  pending_entry_signal_date: null,
  equity_curve: [
    { date: '2024-01-08', cash: 10, position_quantity: 9, position_market_value: 1080, equity: 1090 },
    { date: '2024-01-22', cash: 1180, position_quantity: 0, position_market_value: 0, equity: 1180 },
  ],
}

const ANALYTICS: PerformanceAnalyticsResponse = {
  provider_symbol: 'RELIANCE.NS',
  interval: '1d',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  initial_equity: 1000,
  ending_equity: 1180,
  total_return: 0.18,
  realized_pnl: 180,
  unrealized_pnl: 0,
  total_pnl: 180,
  closed_trade_count: 1,
  winner_count: 1,
  loser_count: 0,
  breakeven_count: 0,
  win_rate: 1,
  average_trade_return: 0.1818,
  median_trade_return: 0.1818,
  best_trade_return: 0.1818,
  worst_trade_return: 0.1818,
  peak_equity: 1180,
  maximum_drawdown: 0,
  max_drawdown_peak_date: '2024-01-22',
  max_drawdown_trough_date: '2024-01-22',
  exposed_bar_count: 1,
  total_bar_count: 2,
  exposure: 0.5,
  drawdown_series: [
    { date: '2024-01-08', equity: 1090, running_peak: 1090, drawdown: 0 },
    { date: '2024-01-22', equity: 1180, running_peak: 1180, drawdown: 0 },
  ],
}

async function runResearch(user: ReturnType<typeof userEvent.setup>) {
  vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [RELIANCE] })
  await user.type(screen.getByRole('combobox'), 'REL')
  const option = await screen.findByText('RELIANCE', {}, { timeout: 1000 })
  await user.click(option)
  await user.click(screen.getByRole('button', { name: 'Run Backtest' }))
}

describe('BacktestsPage route/sidebar integration', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders at /backtests with the sidebar Backtests link present and active', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/backtests'] })

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Backtests' })).toBeInTheDocument())
    const sidebarLink = screen.getAllByRole('link', { name: 'Backtests' })[0]
    expect(sidebarLink).toHaveAttribute('href', '/backtests')
  })

  it('shows a research empty state before the first run', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/backtests'] })

    await waitFor(() =>
      expect(
        screen.getByText('Select an instrument and historical period to evaluate Trend + Momentum v1.'),
      ).toBeInTheDocument(),
    )
  })
})

describe('BacktestsPage research orchestration', () => {
  beforeEach(() => {
    vi.spyOn(outcomesApi, 'getTrendMomentumV1Outcomes').mockResolvedValue(OUTCOMES)
    vi.spyOn(backtestsApi, 'getTrendMomentumV1Backtest').mockResolvedValue(BACKTEST)
    vi.spyOn(analyticsApi, 'getTrendMomentumV1Analytics').mockResolvedValue(ANALYTICS)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function renderPage() {
    return render(
      <ThemeProvider>
        <MemoryRouter>
          <BacktestsPage />
        </MemoryRouter>
      </ThemeProvider>,
    )
  }

  it('running a backtest requests outcomes, backtest, and analytics for the same symbol/date range', async () => {
    const user = userEvent.setup()
    renderPage()
    await runResearch(user)

    await waitFor(() => expect(outcomesApi.getTrendMomentumV1Outcomes).toHaveBeenCalledTimes(1))
    expect(backtestsApi.getTrendMomentumV1Backtest).toHaveBeenCalledTimes(1)
    expect(analyticsApi.getTrendMomentumV1Analytics).toHaveBeenCalledTimes(1)

    const outcomesArgs = vi.mocked(outcomesApi.getTrendMomentumV1Outcomes).mock.calls[0][0]
    const backtestArgs = vi.mocked(backtestsApi.getTrendMomentumV1Backtest).mock.calls[0][0]
    const analyticsArgs = vi.mocked(analyticsApi.getTrendMomentumV1Analytics).mock.calls[0][0]

    expect(outcomesArgs.symbol).toBe('RELIANCE')
    expect(backtestArgs.symbol).toBe('RELIANCE')
    expect(analyticsArgs.symbol).toBe('RELIANCE')
    expect(outcomesArgs.start).toBe(backtestArgs.start)
    expect(outcomesArgs.end).toBe(backtestArgs.end)
    expect(backtestArgs.start).toBe(analyticsArgs.start)
    expect(backtestArgs.end).toBe(analyticsArgs.end)
  })

  it('backtest and analytics requests use identical initial capital', async () => {
    const user = userEvent.setup()
    renderPage()
    await runResearch(user)

    await waitFor(() => expect(backtestsApi.getTrendMomentumV1Backtest).toHaveBeenCalledTimes(1))
    const backtestArgs = vi.mocked(backtestsApi.getTrendMomentumV1Backtest).mock.calls[0][0]
    const analyticsArgs = vi.mocked(analyticsApi.getTrendMomentumV1Analytics).mock.calls[0][0]
    expect(backtestArgs.initialCapital).toBe(analyticsArgs.initialCapital)
    expect(backtestArgs.initialCapital).toBe(100000)
  })

  it('shows a loading state while the three requests are in flight', async () => {
    let resolveOutcomes: (v: SignalOutcomeSeriesResponse) => void = () => {}
    vi.spyOn(outcomesApi, 'getTrendMomentumV1Outcomes').mockReturnValue(
      new Promise((resolve) => (resolveOutcomes = resolve)),
    )
    const user = userEvent.setup()
    renderPage()
    await runResearch(user)

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    resolveOutcomes(OUTCOMES)
    await waitFor(() => expect(screen.queryByRole('status', { name: 'Loading' })).not.toBeInTheDocument())
  })

  it('shows the stable backend error and no partial/mixed result on failure', async () => {
    vi.spyOn(backtestsApi, 'getTrendMomentumV1Backtest').mockRejectedValue(
      new ApiError(404, 'INSTRUMENT_NOT_FOUND', 'Instrument not found.'),
    )
    const user = userEvent.setup()
    renderPage()
    await runResearch(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('Instrument not found.')
    expect(screen.queryByTestId('equity-chart')).not.toBeInTheDocument()
    expect(screen.queryByText('Total Return')).not.toBeInTheDocument()
  })

  it('renders the equity chart from the backtest equity_curve values directly, without recomputation', async () => {
    const user = userEvent.setup()
    renderPage()
    await runResearch(user)

    const chart = await screen.findByTestId('equity-chart-legend')
    expect(chart.textContent).toContain('1,180.00') // final equity point, verbatim from the API response
  })

  it('renders the performance summary using analytics values only', async () => {
    const user = userEvent.setup()
    renderPage()
    await runResearch(user)

    await screen.findByText('Total Return')
    expect(screen.getByText('+18.00%')).toBeInTheDocument()
  })

  it('renders Trades and Signal Outcomes tabs with data from their respective endpoints', async () => {
    const user = userEvent.setup()
    renderPage()
    await runResearch(user)

    await screen.findByRole('tab', { name: 'Trades' })
    expect(screen.getByRole('tab', { name: 'Signal Outcomes' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Drawdown' })).toBeInTheDocument()

    const tradesPanel = screen.getByRole('tabpanel')
    expect(within(tradesPanel).getByText('9')).toBeInTheDocument() // trade quantity

    await user.click(screen.getByRole('tab', { name: 'Signal Outcomes' }))
    expect(screen.getByText('Reference Close')).toBeInTheDocument()
  })

  it('does not overwrite a newer research run with a stale, slower earlier response', async () => {
    // Faithfully simulate the real fetch/AbortController contract: a
    // superseded request's promise must reject with AbortedRequestError
    // once its signal is aborted (exactly what api/client.ts's real fetch
    // call does) -- useApiResource relies on that rejection, not on the
    // mock itself knowing about staleness.
    type PendingCall = { signal?: AbortSignal; settle: () => void }
    const pending: PendingCall[] = []
    const spy = vi.spyOn(backtestsApi, 'getTrendMomentumV1Backtest')
    spy.mockImplementation(
      (args) =>
        new Promise((resolve, reject) => {
          pending.push({
            signal: args.signal,
            settle: () => {
              if (args.signal?.aborted) reject(new AbortedRequestError())
              else resolve(BACKTEST)
            },
          })
        }),
    )

    const user = userEvent.setup()
    renderPage()
    await runResearch(user) // first (slow) run: request #1 now pending, unsettled

    // Trigger a second run (different initial capital, so deps actually
    // change) before the first resolves -- this aborts #1's controller.
    const capitalInput = screen.getByLabelText(/Initial Capital/i)
    await user.clear(capitalInput)
    await user.type(capitalInput, '50000')
    await user.click(screen.getByRole('button', { name: 'Run Backtest' }))
    await waitFor(() => expect(pending).toHaveLength(2))

    // Settle the stale first request AFTER the second was issued -- since
    // its signal is now aborted, it must reject, never overwrite state.
    pending[0].settle()
    pending[1].settle()

    await waitFor(() => expect(screen.getByRole('tabpanel')).toBeInTheDocument())
    expect(within(screen.getByRole('tabpanel')).queryByText('No closed trades in this period.')).not.toBeInTheDocument()
  })
})
