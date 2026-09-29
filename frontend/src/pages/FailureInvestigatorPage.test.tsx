import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../theme/ThemeProvider'
import App from '../App'
import FailureInvestigatorPage from './FailureInvestigatorPage'
import { mockFetchForAuthState, renderWithProviders, TEST_USER } from '../test/authTestUtils'
import * as instrumentsApi from '../api/instruments'
import * as investigationsApi from '../api/investigations'
import { ApiError } from '../api/client'
import type { Instrument, StrategyFailureInvestigationResponse } from '../api/types'

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

const MIXED_INVESTIGATION: StrategyFailureInvestigationResponse = {
  provider_symbol: 'RELIANCE.NS',
  interval: '1d',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  total_signal_count: 5,
  eligible_count: 4,
  failed_count: 2,
  non_failed_count: 2,
  unavailable_count: 1,
  outcome_comparison: {
    failed: {
      count: 2,
      average_forward_return_10d: -0.056667,
      median_forward_return_10d: -0.05,
      average_mae_10d: -0.076667,
      median_mae_10d: -0.08,
      worst_mae_10d: -0.12,
      average_mfe_10d: 0.023333,
      median_mfe_10d: 0.02,
      best_mfe_10d: 0.04,
    },
    non_failed: {
      count: 2,
      average_forward_return_10d: 0.03,
      median_forward_return_10d: 0.02,
      average_mae_10d: -0.0125,
      median_mae_10d: -0.0125,
      worst_mae_10d: -0.02,
      average_mfe_10d: 0.05,
      median_mfe_10d: 0.04,
      best_mfe_10d: 0.1,
    },
  },
  context_analysis: {
    failed: {
      count: 2,
      average_rsi14: 45.333333,
      median_rsi14: 45.0,
      volatility_available_count: 1,
      volatility_unavailable_count: 1,
      average_annualized_realized_volatility_20: 0.31,
      median_annualized_realized_volatility_20: 0.31,
      average_close_above_sma20_fraction: 0.02,
      median_close_above_sma20_fraction: 0.02,
      average_sma20_above_sma50_fraction: 0.06,
      median_sma20_above_sma50_fraction: 0.06,
      bullish_trend_count: 2,
      bearish_trend_count: 0,
      transitional_count: 0,
      insufficient_data_count: 0,
    },
    non_failed: {
      count: 2,
      average_rsi14: 57.5,
      median_rsi14: 57.5,
      volatility_available_count: 2,
      volatility_unavailable_count: 0,
      average_annualized_realized_volatility_20: 0.0001,
      median_annualized_realized_volatility_20: 0.0001,
      average_close_above_sma20_fraction: 0.015,
      median_close_above_sma20_fraction: 0.015,
      average_sma20_above_sma50_fraction: 0.065,
      median_sma20_above_sma50_fraction: 0.065,
      bullish_trend_count: 2,
      bearish_trend_count: 0,
      transitional_count: 0,
      insufficient_data_count: 0,
    },
    observations: [
    {
      signal_date: '2024-01-01',
      classification: 'NEGATIVE',
      regime: 'BULLISH_TREND',
      annualized_realized_volatility_20: 0.31,
      rsi14: 45.0,
      close: 1020.0,
      sma20: 990.0,
      sma50: 900.0,
      close_above_sma20_fraction: 0.0303,
      sma20_above_sma50_fraction: 0.1,
    },
    {
      signal_date: '2024-01-02',
      classification: 'NEGATIVE',
      regime: 'BULLISH_TREND',
      annualized_realized_volatility_20: null,
      rsi14: 50.0,
      close: 1021.0,
      sma20: 1005.0,
      sma50: 950.0,
      close_above_sma20_fraction: 0.0159,
      sma20_above_sma50_fraction: 0.0579,
    },
    {
      signal_date: '2024-01-03',
      classification: 'POSITIVE',
      regime: 'BULLISH_TREND',
      annualized_realized_volatility_20: 0.0001,
      rsi14: 60.0,
      close: 1023.0,
      sma20: 1000.0,
      sma50: 900.0,
      close_above_sma20_fraction: 0.023,
      sma20_above_sma50_fraction: 0.1111,
    },
    {
      signal_date: '2024-01-04',
      classification: 'BREAKEVEN',
      regime: 'BULLISH_TREND',
      annualized_realized_volatility_20: 0.0001,
      rsi14: 55.0,
      close: 1026.0,
      sma20: 1010.0,
      sma50: 950.0,
      close_above_sma20_fraction: 0.0158,
      sma20_above_sma50_fraction: 0.0632,
    },
    {
      signal_date: '2024-01-05',
      classification: 'UNAVAILABLE',
      regime: 'BULLISH_TREND',
      annualized_realized_volatility_20: 0.0001,
      rsi14: 52.0,
      close: 1027.0,
      sma20: 1010.0,
      sma50: 950.0,
      close_above_sma20_fraction: 0.0168,
      sma20_above_sma50_fraction: 0.0632,
    },
    ],
  },
}

const ZERO_SIGNALS: StrategyFailureInvestigationResponse = {
  ...MIXED_INVESTIGATION,
  total_signal_count: 0,
  eligible_count: 0,
  failed_count: 0,
  non_failed_count: 0,
  unavailable_count: 0,
  outcome_comparison: {
    failed: { count: 0, average_forward_return_10d: null, median_forward_return_10d: null, average_mae_10d: null, median_mae_10d: null, worst_mae_10d: null, average_mfe_10d: null, median_mfe_10d: null, best_mfe_10d: null },
    non_failed: { count: 0, average_forward_return_10d: null, median_forward_return_10d: null, average_mae_10d: null, median_mae_10d: null, worst_mae_10d: null, average_mfe_10d: null, median_mfe_10d: null, best_mfe_10d: null },
  },
  context_analysis: {
    failed: { count: 0, average_rsi14: null, median_rsi14: null, volatility_available_count: 0, volatility_unavailable_count: 0, average_annualized_realized_volatility_20: null, median_annualized_realized_volatility_20: null, average_close_above_sma20_fraction: null, median_close_above_sma20_fraction: null, average_sma20_above_sma50_fraction: null, median_sma20_above_sma50_fraction: null, bullish_trend_count: 0, bearish_trend_count: 0, transitional_count: 0, insufficient_data_count: 0 },
    non_failed: { count: 0, average_rsi14: null, median_rsi14: null, volatility_available_count: 0, volatility_unavailable_count: 0, average_annualized_realized_volatility_20: null, median_annualized_realized_volatility_20: null, average_close_above_sma20_fraction: null, median_close_above_sma20_fraction: null, average_sma20_above_sma50_fraction: null, median_sma20_above_sma50_fraction: null, bullish_trend_count: 0, bearish_trend_count: 0, transitional_count: 0, insufficient_data_count: 0 },
    observations: [],
  },
}

const ZERO_FAILED: StrategyFailureInvestigationResponse = {
  ...MIXED_INVESTIGATION,
  failed_count: 0,
  eligible_count: 2,
  total_signal_count: 3,
  outcome_comparison: {
    failed: { count: 0, average_forward_return_10d: null, median_forward_return_10d: null, average_mae_10d: null, median_mae_10d: null, worst_mae_10d: null, average_mfe_10d: null, median_mfe_10d: null, best_mfe_10d: null },
    non_failed: MIXED_INVESTIGATION.outcome_comparison.non_failed,
  },
  context_analysis: {
    failed: { count: 0, average_rsi14: null, median_rsi14: null, volatility_available_count: 0, volatility_unavailable_count: 0, average_annualized_realized_volatility_20: null, median_annualized_realized_volatility_20: null, average_close_above_sma20_fraction: null, median_close_above_sma20_fraction: null, average_sma20_above_sma50_fraction: null, median_sma20_above_sma50_fraction: null, bullish_trend_count: 0, bearish_trend_count: 0, transitional_count: 0, insufficient_data_count: 0 },
    non_failed: MIXED_INVESTIGATION.context_analysis.non_failed,
    observations: MIXED_INVESTIGATION.context_analysis.observations.filter((o) => o.classification !== 'NEGATIVE'),
  },
}

const ZERO_NON_FAILED: StrategyFailureInvestigationResponse = {
  ...MIXED_INVESTIGATION,
  non_failed_count: 0,
  eligible_count: 2,
  total_signal_count: 3,
  outcome_comparison: {
    failed: MIXED_INVESTIGATION.outcome_comparison.failed,
    non_failed: { count: 0, average_forward_return_10d: null, median_forward_return_10d: null, average_mae_10d: null, median_mae_10d: null, worst_mae_10d: null, average_mfe_10d: null, median_mfe_10d: null, best_mfe_10d: null },
  },
  context_analysis: {
    failed: MIXED_INVESTIGATION.context_analysis.failed,
    non_failed: { count: 0, average_rsi14: null, median_rsi14: null, volatility_available_count: 0, volatility_unavailable_count: 0, average_annualized_realized_volatility_20: null, median_annualized_realized_volatility_20: null, average_close_above_sma20_fraction: null, median_close_above_sma20_fraction: null, average_sma20_above_sma50_fraction: null, median_sma20_above_sma50_fraction: null, bullish_trend_count: 0, bearish_trend_count: 0, transitional_count: 0, insufficient_data_count: 0 },
    observations: MIXED_INVESTIGATION.context_analysis.observations.filter(
      (o) => o.classification === 'NEGATIVE' || o.classification === 'UNAVAILABLE',
    ),
  },
}

const ALL_UNAVAILABLE: StrategyFailureInvestigationResponse = {
  ...MIXED_INVESTIGATION,
  total_signal_count: 2,
  eligible_count: 0,
  failed_count: 0,
  non_failed_count: 0,
  unavailable_count: 2,
  outcome_comparison: ZERO_SIGNALS.outcome_comparison,
  context_analysis: {
    ...ZERO_SIGNALS.context_analysis,
    observations: [
      { ...MIXED_INVESTIGATION.context_analysis.observations[4], signal_date: '2024-01-01' },
      { ...MIXED_INVESTIGATION.context_analysis.observations[4], signal_date: '2024-01-02' },
    ],
  },
}

async function runInvestigation(user: ReturnType<typeof userEvent.setup>) {
  vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [RELIANCE] })
  await user.type(screen.getByRole('combobox'), 'REL')
  const option = await screen.findByText('RELIANCE', {}, { timeout: 1000 })
  await user.click(option)
  await user.click(screen.getByRole('button', { name: 'Run Investigation' }))
}

function renderPage() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <FailureInvestigatorPage />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('Failure Investigator route/sidebar integration', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders at /failure-investigator with the sidebar link present and active', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Strategy Failure Investigator' })).toBeInTheDocument())
    const sidebarLink = screen.getAllByRole('link', { name: 'Failure Investigator' })[0]
    expect(sidebarLink).toHaveAttribute('href', '/failure-investigator')
  })

  it('shows an empty state before the first investigation is run', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })

    await waitFor(() =>
      expect(
        screen.getByText('Select an instrument and historical date range to run a strategy failure investigation.'),
      ).toBeInTheDocument(),
    )
  })

  it('keeps the Strategy Auditor route separate and unaffected', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Strategy Auditor' })).toBeInTheDocument())
  })
})

describe('Failure Investigator API integration', () => {
  beforeEach(() => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(MIXED_INVESTIGATION)
  })
  afterEach(() => vi.restoreAllMocks())

  it('issues a typed request with the correct symbol/interval', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await waitFor(() => expect(investigationsApi.getTrendMomentumV1Investigation).toHaveBeenCalledTimes(1))
    const args = vi.mocked(investigationsApi.getTrendMomentumV1Investigation).mock.calls[0][0]
    expect(args.symbol).toBe('RELIANCE')
    expect(args.interval).toBe('1d')
    expect(args.start).toBeTruthy()
    expect(args.end).toBeTruthy()
  })

  it('shows a loading state while the request is in flight', async () => {
    let resolve: (v: StrategyFailureInvestigationResponse) => void = () => {}
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockReturnValue(new Promise((r) => (resolve = r)))
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    resolve(MIXED_INVESTIGATION)
    await waitFor(() => expect(screen.queryByRole('status', { name: 'Loading' })).not.toBeInTheDocument())
  })

  it('shows the stable backend error on API failure', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockRejectedValue(
      new ApiError(500, 'INTERNAL_DATA_CONTRACT_ERROR', 'Internal error.'),
    )
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('Internal error.')
    expect(screen.queryByText('Population Overview')).not.toBeInTheDocument()
  })
})

describe('Failure Investigator population overview', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders exact backend population counts', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(MIXED_INVESTIGATION)
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Population Overview')
    expect(screen.getByText('Total BUY Signals').closest('div')?.parentElement?.textContent).toContain('5')
    expect(screen.getByText('Eligible 10-Bar Outcomes').closest('div')?.parentElement?.textContent).toContain('4')
    const failedCards = screen.getAllByText('Failed')
    expect(failedCards.length).toBeGreaterThan(0)
  })

  it('renders zero-total-signal state without fabricated comparisons', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(ZERO_SIGNALS)
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    expect(await screen.findByText(/No historical BUY signals were found/)).toBeInTheDocument()
    expect(screen.queryByText('Retrospective Outcome Comparison')).not.toBeInTheDocument()
  })

  it('renders zero-failed-population state with neutral copy, not zero metrics', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(ZERO_FAILED)
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Retrospective Outcome Comparison')
    expect(screen.getAllByText('No failed signals were present in this research window.').length).toBeGreaterThan(0)
    expect(screen.queryByText('0.00%')).not.toBeInTheDocument()
  })

  it('renders zero-non-failed-population state with neutral copy', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(ZERO_NON_FAILED)
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Retrospective Outcome Comparison')
    expect(screen.getAllByText('No non-failed signals were present in this research window.').length).toBeGreaterThan(0)
  })

  it('renders all-unavailable population correctly', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(ALL_UNAVAILABLE)
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Retrospective Outcome Comparison')
    expect(screen.getAllByText('No failed signals were present in this research window.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No non-failed signals were present in this research window.').length).toBeGreaterThan(0)
    const rows = screen.getAllByText('Unavailable')
    expect(rows.length).toBeGreaterThan(0)
  })
})

describe('Failure Investigator outcome comparison', () => {
  beforeEach(() => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(MIXED_INVESTIGATION)
  })
  afterEach(() => vi.restoreAllMocks())

  it('renders failed and non-failed outcome metrics from the backend, formatted as percentages with signs', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    const section = (await screen.findByText('Retrospective Outcome Comparison')).closest('div')!.parentElement!
    expect(within(section).getByText('Observed after each historical signal.')).toBeInTheDocument()
    // -0.056667 -> -5.67%
    expect(within(section).getByText('-5.67%')).toBeInTheDocument()
    // 0.03 -> +3.00%
    expect(within(section).getByText('+3.00%')).toBeInTheDocument()
  })

  it('preserves signed MAE (never abs())', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    const section = (await screen.findByText('Retrospective Outcome Comparison')).closest('div')!.parentElement!
    // worst_mae_10d = -0.12 -> -12.00%, must stay negative
    expect(within(section).getByText('-12.00%')).toBeInTheDocument()
  })

  it('preserves signed MFE', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    const section = (await screen.findByText('Retrospective Outcome Comparison')).closest('div')!.parentElement!
    // best_mfe_10d non_failed = 0.10 -> +10.00%
    expect(within(section).getByText('+10.00%')).toBeInTheDocument()
  })

  it('never renders a computed difference or winner column', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Retrospective Outcome Comparison')
    expect(screen.queryByText(/winner/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/difference/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/better|worse|stronger|safer|superior/i)).not.toBeInTheDocument()
  })
})

describe('Failure Investigator context comparison', () => {
  beforeEach(() => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(MIXED_INVESTIGATION)
  })
  afterEach(() => vi.restoreAllMocks())

  it('renders RSI average/median from the backend', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    const section = (await screen.findByText('Signal-Time Context Comparison')).closest('div')!.parentElement!
    expect(within(section).getByText('Values available when each historical signal fired.')).toBeInTheDocument()
    expect(within(section).getByText('45.00')).toBeInTheDocument()
  })

  it('renders volatility available/unavailable counts and avg/median', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    const section = (await screen.findByText('Signal-Time Context Comparison')).closest('div')!.parentElement!
    expect(within(section).getByText('1 / 1')).toBeInTheDocument()
    expect(within(section).getByText('2 / 0')).toBeInTheDocument()
  })

  it('renders close/SMA20 and SMA20/SMA50 fraction comparisons as percentages', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    const section = (await screen.findByText('Signal-Time Context Comparison')).closest('div')!.parentElement!
    // average_close_above_sma20_fraction and median_close_above_sma20_fraction (failed) are both 0.02 -> +2.00%
    expect(within(section).getAllByText('+2.00%').length).toBeGreaterThan(0)
  })

  it('renders regime counts', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Bullish Trend Count')
    expect(screen.getByText('Bearish Trend Count')).toBeInTheDocument()
    expect(screen.getByText('Transitional Count')).toBeInTheDocument()
    expect(screen.getByText('Insufficient Data Count')).toBeInTheDocument()
  })

  it('never computes a FAILED-minus-NON_FAILED difference', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Signal-Time Context Comparison')
    expect(screen.queryByText(/difference/i)).not.toBeInTheDocument()
  })
})

describe('Failure Investigator historical signal evidence table', () => {
  beforeEach(() => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(MIXED_INVESTIGATION)
  })
  afterEach(() => vi.restoreAllMocks())

  it('preserves backend observation order', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    const dateCells = screen.getAllByText(/^\d{2} Jan 2024$/)
    expect(dateCells.length).toBe(5)
  })

  it('maps NEGATIVE to the Failed badge', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0)
  })

  it('maps POSITIVE to the Positive badge, never Success', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    expect(screen.getAllByText('Positive').length).toBeGreaterThan(0)
    expect(screen.queryByText('Success')).not.toBeInTheDocument()
  })

  it('maps BREAKEVEN to the Breakeven badge', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    expect(screen.getAllByText('Breakeven').length).toBeGreaterThan(0)
  })

  it('maps UNAVAILABLE to the Unavailable badge', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
  })

  it('renders human-readable regime labels', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    expect(screen.getAllByText('Bullish Trend').length).toBeGreaterThan(0)
  })

  it('renders a null observation volatility as unavailable, never 0%', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0)
  })

  it('the All filter shows every row', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    expect(screen.getByText('5 of 5 rows')).toBeInTheDocument()
  })

  it('the Failed filter shows only NEGATIVE rows', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    await user.click(screen.getByRole('button', { name: 'Failed', pressed: false }))
    expect(screen.getByText('2 of 5 rows')).toBeInTheDocument()
  })

  it('the Non-Failed filter includes POSITIVE + BREAKEVEN', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    await user.click(screen.getByRole('button', { name: 'Non-Failed', pressed: false }))
    expect(screen.getByText('2 of 5 rows')).toBeInTheDocument()
  })

  it('the Unavailable filter shows only UNAVAILABLE rows', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    await user.click(screen.getByRole('button', { name: 'Unavailable', pressed: false }))
    expect(screen.getByText('1 of 5 rows')).toBeInTheDocument()
  })

  it('filtering rows does not alter the population summary values', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    await user.click(screen.getByRole('button', { name: 'Failed', pressed: false }))

    expect(screen.getByText('Total BUY Signals').closest('div')?.parentElement?.textContent).toContain('5')
  })

  it('filtering rows does not alter the outcome/context comparison summary values', async () => {
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)

    await screen.findByText('Historical Signal Evidence')
    const outcomeSection = (await screen.findByText('Retrospective Outcome Comparison')).closest('div')!.parentElement!
    const before = within(outcomeSection).getByText('-5.67%')
    expect(before).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Unavailable', pressed: false }))

    expect(within(outcomeSection).getByText('-5.67%')).toBeInTheDocument()
  })
})

describe('Failure Investigator boundaries / semantics', () => {
  afterEach(() => vi.restoreAllMocks())

  it('describes FAILED as strictly negative 10-trading-bar return', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })
    await waitFor(() =>
      expect(screen.getByText(/10-trading-bar forward return strictly negative/)).toBeInTheDocument(),
    )
  })

  it('describes NON_FAILED as positive or breakeven', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })
    await waitFor(() => expect(screen.getByText(/Positive or breakeven 10-bar outcome/)).toBeInTheDocument())
  })

  it('explains UNAVAILABLE as insufficient forward bars', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })
    const matches = await screen.findAllByText(/Insufficient forward trading bars inside the selected research window/)
    expect(matches.length).toBeGreaterThan(0)
  })

  it('identifies retrospective outcome as post-signal', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(MIXED_INVESTIGATION)
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)
    expect(await screen.findByText(/Observed after each historical signal/)).toBeInTheDocument()
  })

  it('identifies context as signal-time', async () => {
    vi.spyOn(investigationsApi, 'getTrendMomentumV1Investigation').mockResolvedValue(MIXED_INVESTIGATION)
    const user = userEvent.setup()
    renderPage()
    await runInvestigation(user)
    expect(await screen.findByText(/Values available when each historical signal fired/)).toBeInTheDocument()
  })

  it('never uses causal language anywhere on the page', async () => {
    mockFetchForAuthState(TEST_USER)
    const { container } = renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Strategy Failure Investigator' })).toBeInTheDocument())
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/\bcaused\b|\bcauses\b|\bbecause of\b/i)
  })

  it('never uses predictive/confidence language anywhere on the page, aside from the required disclaimer that predictive claims are NOT made', async () => {
    mockFetchForAuthState(TEST_USER)
    const { container } = renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Strategy Failure Investigator' })).toBeInTheDocument())
    // The one approved use of "predict" is the required negating disclaimer
    // itself ("...do not establish causation or predict future outcomes.");
    // strip it out, then assert no other predictive/confidence language
    // remains anywhere on the page.
    const text = (container.textContent ?? '').replace(
      /Historical associations are descriptive and do not establish causation or predict future outcomes\./,
      '',
    )
    expect(text).not.toMatch(/predict|confidence score|will (fail|succeed)/i)
  })
})
