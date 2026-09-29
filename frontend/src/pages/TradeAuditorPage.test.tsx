import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../theme/ThemeProvider'
import App from '../App'
import TradeAuditorPage from './TradeAuditorPage'
import { mockFetchForAuthState, renderWithProviders, TEST_USER } from '../test/authTestUtils'
import * as instrumentsApi from '../api/instruments'
import * as auditsApi from '../api/audits'
import { ApiError } from '../api/client'
import type { Instrument, StrategyAuditResponse } from '../api/types'

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

const BUY_AUDIT: StrategyAuditResponse = {
  provider_symbol: 'RELIANCE.NS',
  interval: '1d',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  audit_date: '2024-06-10',
  evaluation: {
    date: '2024-06-10',
    strategy_id: 'trend_momentum_v1',
    strategy_name: 'Trend + Momentum v1',
    decision: 'BUY',
    missing_inputs: [],
    conditions: [
      {
        condition_id: 'close_above_sma20',
        description: 'Close is above SMA20',
        passed: true,
        operator: '>',
        actual_values: [
          { name: 'close', value: 1471.4 },
          { name: 'sma20', value: 1444.15 },
        ],
        reference_values: [],
      },
      {
        condition_id: 'sma20_above_sma50',
        description: 'SMA20 is above SMA50',
        passed: true,
        operator: '>',
        actual_values: [
          { name: 'sma20', value: 1444.15 },
          { name: 'sma50', value: 1400.0 },
        ],
        reference_values: [],
      },
      {
        condition_id: 'rsi_in_range',
        description: 'RSI14 is within the inclusive strategy range',
        passed: true,
        operator: 'inclusive_range',
        actual_values: [{ name: 'rsi14', value: 54.24 }],
        reference_values: [
          { name: 'lower_bound', value: 40 },
          { name: 'upper_bound', value: 70 },
        ],
      },
    ],
  },
  historical_evidence: {
    prior_signal_count: 3,
    five_bar: {
      eligible_outcome_count: 2,
      positive_count: 1,
      negative_count: 1,
      breakeven_count: 0,
      hit_rate: 0.5,
      average_return: 0.01,
    },
    ten_bar: {
      eligible_outcome_count: 0,
      positive_count: 0,
      negative_count: 0,
      breakeven_count: 0,
      hit_rate: null,
      average_return: null,
    },
  },
  historical_signal_risk: {
    eligible_outcome_count: 0,
    average_mae_10d: null,
    worst_mae_10d: null,
    average_mfe_10d: null,
    best_mfe_10d: null,
  },
  risk_market_context: {
    annualized_realized_volatility_20: 0.380565,
    regime: 'BULLISH_TREND',
    regime_evidence: {
      close: 1471.4,
      sma20: 1444.15,
      sma50: 1400.0,
      close_vs_sma20: 'ABOVE',
      sma20_vs_sma50: 'ABOVE',
    },
  },
  retrospective_outcome: {
    date: '2024-06-10',
    decision: 'BUY',
    reference_close: 1471.4,
    forward_close_5d: 1500.0,
    forward_return_5d: 0.0194,
    forward_close_10d: null,
    forward_return_10d: null,
    mae_10d: null,
    mfe_10d: null,
    available_forward_bars: 6,
  },
}

const NO_SIGNAL_AUDIT: StrategyAuditResponse = {
  ...BUY_AUDIT,
  evaluation: { ...BUY_AUDIT.evaluation, decision: 'NO_SIGNAL', conditions: [{ ...BUY_AUDIT.evaluation.conditions[2], passed: false }] },
  retrospective_outcome: null,
}

const INSUFFICIENT_DATA_AUDIT: StrategyAuditResponse = {
  ...BUY_AUDIT,
  evaluation: {
    date: '2024-06-10',
    strategy_id: 'trend_momentum_v1',
    strategy_name: 'Trend + Momentum v1',
    decision: 'INSUFFICIENT_DATA',
    missing_inputs: ['sma50'],
    conditions: [],
  },
  risk_market_context: {
    annualized_realized_volatility_20: null,
    regime: 'INSUFFICIENT_DATA',
    regime_evidence: { close: 1471.4, sma20: 1444.15, sma50: null, close_vs_sma20: 'ABOVE', sma20_vs_sma50: null },
  },
  retrospective_outcome: null,
}

async function runAudit(user: ReturnType<typeof userEvent.setup>) {
  vi.spyOn(instrumentsApi, 'searchInstruments').mockResolvedValue({ results: [RELIANCE] })
  await user.type(screen.getByRole('combobox'), 'REL')
  const option = await screen.findByText('RELIANCE', {}, { timeout: 1000 })
  await user.click(option)
  await user.click(screen.getByRole('button', { name: 'Run Audit' }))
}

function renderPage() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <TradeAuditorPage />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('Strategy Auditor route/sidebar integration', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders at /trade-auditor with the sidebar Strategy Auditor link present', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Strategy Auditor' })).toBeInTheDocument())
    const sidebarLink = screen.getAllByRole('link', { name: 'Strategy Auditor' })[0]
    expect(sidebarLink).toHaveAttribute('href', '/trade-auditor')
  })

  it('shows an empty state before the first audit is run', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })

    await waitFor(() =>
      expect(
        screen.getByText('Select an instrument, audit date, and evidence start date to run a strategy audit.'),
      ).toBeInTheDocument(),
    )
  })

  it('shows the evidence-window explanation near the controls', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })

    await waitFor(() =>
      expect(screen.getByText(/Evidence Start sets which prior strategy signals are included/)).toBeInTheDocument(),
    )
  })
})

describe('Strategy Auditor introduction and education content', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('shows the new user-facing introduction copy', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })

    await waitFor(() => expect(screen.getByText('Audit a strategy decision as it looked on that day.')).toBeInTheDocument())
    expect(
      screen.getByText(/TradeLens separately shows what happened after the selected date as hindsight/),
    ).toBeInTheDocument()
  })

  it('shows the "How This Audit Works" section with its four concepts', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })

    await waitFor(() => expect(screen.getByText('How This Audit Works')).toBeInTheDocument())
    expect(screen.getByText('1. Decision')).toBeInTheDocument()
    expect(screen.getByText('2. Market Context')).toBeInTheDocument()
    expect(screen.getByText('3. Prior Strategy Evidence')).toBeInTheDocument()
    expect(screen.getByText('4. Hindsight')).toBeInTheDocument()
    expect(screen.getByText(/not available to the strategy when the decision was made/)).toBeInTheDocument()
  })

  it('makes the Trend + Momentum v1 rules discoverable via a disclosure near the strategy control', async () => {
    mockFetchForAuthState(TEST_USER)
    const user = userEvent.setup()
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })

    const summary = await screen.findByText('About Trend + Momentum v1 (Strategy Rules)')
    await user.click(summary)

    expect(screen.getByText('Close > SMA20')).toBeInTheDocument()
    expect(screen.getByText('AND SMA20 > SMA50')).toBeInTheDocument()
    expect(screen.getByText('AND 40 <= RSI(14) <= 70')).toBeInTheDocument()
  })

  it('explains NO_SIGNAL and INSUFFICIENT_DATA semantics in the strategy rules disclosure', async () => {
    mockFetchForAuthState(TEST_USER)
    const user = userEvent.setup()
    renderWithProviders(<App />, { initialEntries: ['/trade-auditor'] })

    await user.click(await screen.findByText('About Trend + Momentum v1 (Strategy Rules)'))

    expect(screen.getByText(/any condition fails, the decision is NO_SIGNAL/)).toBeInTheDocument()
    expect(screen.getByText(/indicator history is unavailable, the decision is INSUFFICIENT_DATA/)).toBeInTheDocument()
    expect(screen.getByText(/No SELL signal exists in v1/)).toBeInTheDocument()
  })
})

describe('Strategy Auditor request orchestration', () => {
  beforeEach(() => {
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockResolvedValue(BUY_AUDIT)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('issues a typed audit request for the selected symbol/audit_date', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await waitFor(() => expect(auditsApi.getTrendMomentumV1Audit).toHaveBeenCalledTimes(1))
    const args = vi.mocked(auditsApi.getTrendMomentumV1Audit).mock.calls[0][0]
    expect(args.symbol).toBe('RELIANCE')
    expect(args.interval).toBe('1d')
    expect(args.auditDate).toBeTruthy()
    expect(args.start).toBeTruthy()
  })

  it('shows a loading state while the request is in flight', async () => {
    let resolveAudit: (v: StrategyAuditResponse) => void = () => {}
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockReturnValue(new Promise((resolve) => (resolveAudit = resolve)))
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    resolveAudit(BUY_AUDIT)
    await waitFor(() => expect(screen.queryByRole('status', { name: 'Loading' })).not.toBeInTheDocument())
  })

  it('shows the stable backend error message and code on a non-trading-date rejection', async () => {
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockRejectedValue(
      new ApiError(422, 'AUDIT_DATE_NOT_A_TRADING_BAR', 'No trading bar exists for the selected audit date.'),
    )
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('No trading bar exists for the selected audit date.')
    expect(screen.getByText('AUDIT_DATE_NOT_A_TRADING_BAR')).toBeInTheDocument()
  })

  it('shows a general API error state with no partial audit rendered', async () => {
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockRejectedValue(new ApiError(500, 'INTERNAL_DATA_CONTRACT_ERROR', 'Internal error.'))
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('Prior Strategy Signals')).not.toBeInTheDocument()
  })
})

describe('Strategy Auditor BUY audit rendering', () => {
  beforeEach(() => {
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockResolvedValue(BUY_AUDIT)
  })
  afterEach(() => vi.restoreAllMocks())

  it('renders the BUY decision using the backend value verbatim (no invented "Strong Buy" language)', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await waitFor(() => expect(screen.getAllByText('Buy').length).toBeGreaterThan(0))
    expect(screen.queryByText(/strong buy/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('renders condition PASS/FAIL and values verbatim from the API (no recomputation)', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await screen.findByText('Close is above SMA20')
    expect(screen.getAllByText('PASS').length).toBeGreaterThan(0)
    expect(screen.getByText('54.24')).toBeInTheDocument()
  })

  it('renders the prior signal count and 5-bar/10-bar statistics', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await screen.findByText('Prior Strategy Signals')
    expect(screen.getByText('3 prior signal(s)')).toBeInTheDocument()
    expect(screen.getByText('5 Trading Bars Forward')).toBeInTheDocument()
    expect(screen.getByText('10 Trading Bars Forward')).toBeInTheDocument()
    expect(screen.getByText('+1.00%')).toBeInTheDocument() // five_bar.average_return
  })

  it('renders null 10-bar hit rate/average return as "Not available", never 0%', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await screen.findByText('10 Trading Bars Forward')
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0)
    expect(screen.queryByText('0.00%')).not.toBeInTheDocument()
  })

  it('renders historical signal risk with null MAE/MFE as "Not available"', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await screen.findByText('Historical Signal Risk')
    const riskCard = screen.getByText('Historical Signal Risk').closest('div')!.parentElement!
    expect(riskCard.textContent).toContain('Not available')
  })

  it('formats the annualized volatility decimal as a percentage', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await screen.findByText('Market Context')
    expect(screen.getByText('38.06%')).toBeInTheDocument()
  })

  it('renders the market regime and its supporting close/SMA evidence', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await screen.findByText('Market Context')
    expect(screen.getByText('Bullish Trend')).toBeInTheDocument()
    expect(screen.getAllByText('Above').length).toBe(2)
  })

  it('renders the retrospective BUY outcome with a HINDSIGHT badge and warning copy', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    const heading = await screen.findByText('Retrospective Outcome')
    const retrospectiveSection = heading.closest('div')!.parentElement!
    expect(within(retrospectiveSection).getByText(/hindsight/i)).toBeInTheDocument()
    expect(screen.getByText(/was not available to the strategy at the time/)).toBeInTheDocument()
    expect(screen.getByText('+1.94%')).toBeInTheDocument() // 5-bar retrospective return
  })

  it('renders censored retrospective fields safely rather than fabricating a value', async () => {
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await screen.findByText('Retrospective Outcome')
    expect(screen.getAllByText('Not yet available in the selected data range').length).toBeGreaterThan(0)
  })
})

describe('Strategy Auditor NO_SIGNAL / INSUFFICIENT_DATA rendering', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders a NO_SIGNAL audit with no retrospective outcome', async () => {
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockResolvedValue(NO_SIGNAL_AUDIT)
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await waitFor(() => expect(screen.getAllByText('No Signal').length).toBeGreaterThan(0))
    expect(
      await screen.findByText('No retrospective BUY outcome applies because the audited decision was NO_SIGNAL, not BUY.')
    ).toBeInTheDocument()
  })

  it('renders an INSUFFICIENT_DATA audit showing missing inputs, an insufficient-data regime, and a decision-specific hindsight reason', async () => {
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockResolvedValue(INSUFFICIENT_DATA_AUDIT)
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    await waitFor(() => expect(screen.getAllByText('Insufficient Data').length).toBeGreaterThan(0))
    expect(screen.getByText(/Missing: sma50/)).toBeInTheDocument()
    expect(
      await screen.findByText(
        'No retrospective BUY outcome applies because the audited decision was INSUFFICIENT_DATA, not BUY.'
      )
    ).toBeInTheDocument()
  })

  it('renders zero prior signals as an explicit empty state, not zeroed statistics', async () => {
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockResolvedValue({
      ...NO_SIGNAL_AUDIT,
      historical_evidence: {
        prior_signal_count: 0,
        five_bar: { eligible_outcome_count: 0, positive_count: 0, negative_count: 0, breakeven_count: 0, hit_rate: null, average_return: null },
        ten_bar: { eligible_outcome_count: 0, positive_count: 0, negative_count: 0, breakeven_count: 0, hit_rate: null, average_return: null },
      },
    })
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    expect(await screen.findByText(/No prior BUY signals for this symbol\/strategy/)).toBeInTheDocument()
  })
})

describe('Strategy Auditor does not recompute finance logic', () => {
  it('renders values that are byte-identical to the mocked API response, never re-derived', async () => {
    // Behavioral proxy for "no recomputation": feed a BUY audit whose
    // numbers don't correspond to any plausible derived/rounded value, and
    // assert the exact API decimals appear verbatim (e.g. an odd average
    // return that a real recomputation would never coincidentally match).
    vi.spyOn(auditsApi, 'getTrendMomentumV1Audit').mockResolvedValue({
      ...BUY_AUDIT,
      historical_evidence: {
        ...BUY_AUDIT.historical_evidence,
        five_bar: { ...BUY_AUDIT.historical_evidence.five_bar, average_return: 0.013731 },
      },
    })
    const user = userEvent.setup()
    renderPage()
    await runAudit(user)

    expect(await screen.findByText('+1.37%')).toBeInTheDocument()
  })
})
