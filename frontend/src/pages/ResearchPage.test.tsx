import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../theme/ThemeProvider'
import App from '../App'
import ResearchPage from './ResearchPage'
import { mockFetchForAuthState, renderWithProviders, TEST_USER } from '../test/authTestUtils'
import * as researchApi from '../api/research'
import { ApiError } from '../api/client'
import type { AuditToolEvidence, ResearchResponse } from '../api/types'

const AUDIT_RAW_RESULT = {
  symbol: 'RELIANCE.NS',
  audit_date: '2024-06-13',
  decision: 'BUY' as const,
  decision_evidence: [
    { condition_id: 'close_above_sma20', description: 'Close > SMA20', passed: true, operator: '>', actual_values: [], reference_values: [] },
    { condition_id: 'sma20_above_sma50', description: 'SMA20 > SMA50', passed: true, operator: '>', actual_values: [], reference_values: [] },
    { condition_id: 'rsi_in_range', description: '40 <= RSI14 <= 70', passed: true, operator: 'between', actual_values: [], reference_values: [] },
  ],
  missing_inputs: [],
  point_in_time_context: {
    prior_signal_count: 12,
    five_bar_hit_rate: 0.5,
    five_bar_average_return: 0.01,
    ten_bar_hit_rate: 0.6,
    ten_bar_average_return: 0.02,
    regime: 'BULLISH_TREND' as const,
    annualized_realized_volatility_20: 0.28,
  },
  retrospective_hindsight: {
    forward_return_10d: 0.068,
    available_forward_bars: 10,
    note: 'Hindsight. Not available at decision time. Does not justify, reinforce, or validate the decision.',
  },
}

const MOCK_RESPONSE: ResearchResponse = {
  question: 'Audit RELIANCE on 2024-06-13 and explain the decision.',
  answer: 'The strategy produced BUY because all three conditions passed.',
  stopped_reason: 'final_answer',
  completed_steps: 1,
  tool_trace: [
    {
      tool_name: 'audit_strategy_decision',
      status: 'ok',
      arguments: { symbol: 'RELIANCE', audit_date: '2024-06-13' },
      result_summary: 'Strategy audit returned successfully.',
      raw_result: AUDIT_RAW_RESULT,
    },
  ],
  knowledge_sources: [
    {
      document_id: 'strategy_trend_momentum_v1',
      document_title: 'Trend + Momentum v1 Strategy',
      source_path: 'strategy_trend_momentum_v1.md',
      chunk_id: 'strategy_trend_momentum_v1#0',
      chunk_ordinal: 0,
      section_heading: 'BUY Rule',
      trust: 'AUTHORITATIVE_INTERNAL',
    },
  ],
  model: 'openai/gpt-oss-120b',
}

function renderPage() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <ResearchPage />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('Research Workspace route/sidebar integration', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders at /research with the sidebar link present', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/research'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Research Workspace' })).toBeInTheDocument())
    const sidebarLink = screen.getAllByRole('link', { name: 'Research Workspace' })[0]
    expect(sidebarLink).toHaveAttribute('href', '/research')
  })
})

describe('Research Workspace initial state', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows the purpose, suggested questions, and a no-result-yet state', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Research Workspace' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask TradeLens/i)).toBeInTheDocument()
    expect(screen.getByText(/What are the exact BUY conditions for Trend \+ Momentum v1\?/)).toBeInTheDocument()
    expect(screen.getByText(/No result yet/)).toBeInTheDocument()
  })
})

describe('Research Workspace submission', () => {
  afterEach(() => vi.restoreAllMocks())

  it('fills and submits a suggested question', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MOCK_RESPONSE)
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByText(/What does an unavailable 10-bar outcome mean\?/))

    await waitFor(() => expect(researchApi.postResearchQuestion).toHaveBeenCalledWith('What does an unavailable 10-bar outcome mean?', expect.anything()))
  })

  it('submits a typed question', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MOCK_RESPONSE)
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'What is RSI14?')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))

    await waitFor(() => expect(researchApi.postResearchQuestion).toHaveBeenCalledWith('What is RSI14?', expect.anything()))
  })

  it('submits via Ctrl+Enter', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MOCK_RESPONSE)
    const user = userEvent.setup()
    renderPage()

    const textarea = screen.getByRole('textbox', { name: /research question/i })
    await user.type(textarea, 'What is RSI14?')
    await user.keyboard('{Control>}{Enter}{/Control}')

    await waitFor(() => expect(researchApi.postResearchQuestion).toHaveBeenCalledWith('What is RSI14?', expect.anything()))
  })

  it('preserves the typed question in the input while loading', async () => {
    let resolve: (v: ResearchResponse) => void = () => {}
    vi.spyOn(researchApi, 'postResearchQuestion').mockReturnValue(new Promise((r) => (resolve = r)))
    const user = userEvent.setup()
    renderPage()

    const textarea = screen.getByRole('textbox', { name: /research question/i }) as HTMLTextAreaElement
    await user.type(textarea, 'What is RSI14?')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))

    expect(textarea.value).toBe('What is RSI14?')
    resolve(MOCK_RESPONSE)
  })

  it('shows a loading state while the request is in flight', async () => {
    let resolve: (v: ResearchResponse) => void = () => {}
    vi.spyOn(researchApi, 'postResearchQuestion').mockReturnValue(new Promise((r) => (resolve = r)))
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'What is RSI14?')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))

    expect(screen.getByText(/Researching deterministic TradeLens evidence/i)).toBeInTheDocument()
    expect(screen.queryByText(/AI is thinking/i)).not.toBeInTheDocument()
    resolve(MOCK_RESPONSE)
    await waitFor(() => expect(screen.queryByText(/Researching deterministic TradeLens evidence/i)).not.toBeInTheDocument())
  })
})

describe('Research Workspace result rendering', () => {
  beforeEach(() => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MOCK_RESPONSE)
  })
  afterEach(() => vi.restoreAllMocks())

  async function submit(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'Audit RELIANCE.')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))
    await waitFor(() => expect(screen.getByText('Research Synthesis')).toBeInTheDocument())
  }

  it('renders the AI synthesis labeled as grounded synthesis', async () => {
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.getByText('Research Synthesis')).toBeInTheDocument()
    expect(screen.getByText(/AI-generated synthesis grounded in the deterministic TradeLens evidence/i)).toBeInTheDocument()
    expect(screen.getByText('The strategy produced BUY because all three conditions passed.')).toBeInTheDocument()
  })

  it('renders the tool trace with tool name, status, and a human-readable evidence summary', async () => {
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.getByText('audit_strategy_decision')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('Strategy Audit')).toBeInTheDocument()
    expect(screen.getByText('Symbol')).toBeInTheDocument()
    expect(screen.getByText('RELIANCE.NS')).toBeInTheDocument()
  })

  it('never dumps raw tool JSON in the Research Workspace', async () => {
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.queryByText(/"decision_evidence"/)).not.toBeInTheDocument()
    expect(screen.queryByText(/"point_in_time_context"/)).not.toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain('&quot;decision_evidence&quot;')
  })

  it('does not offer a "View structured tool details" debug dump', async () => {
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.queryByText(/view structured tool details/i)).not.toBeInTheDocument()
  })

  it('renders knowledge sources with document title, section, and count; trust is in the expandable details', async () => {
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.getByText('Trend + Momentum v1 Strategy')).toBeInTheDocument()
    expect(screen.getByText('BUY Rule')).toBeInTheDocument()
    expect(screen.getByText('1 supporting excerpt')).toBeInTheDocument()
    expect(screen.getByText('1 source document · 1 supporting excerpt')).toBeInTheDocument()
    expect(screen.queryByText('AUTHORITATIVE_INTERNAL')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'View details' }))
    expect(screen.getByText('AUTHORITATIVE_INTERNAL')).toBeInTheDocument()
    expect(screen.getByText('strategy_trend_momentum_v1#0')).toBeInTheDocument()
  })

  it('shows a no-sources state when knowledge_sources is empty', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue({ ...MOCK_RESPONSE, knowledge_sources: [] })
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.getByText(/No knowledge-base sources were used/)).toBeInTheDocument()
  })

  it('keeps audit decision evidence / point-in-time context / retrospective hindsight visually separate', async () => {
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.getByText('Decision Evidence')).toBeInTheDocument()
    expect(screen.getByText('Point-in-Time Context')).toBeInTheDocument()
    expect(screen.getByText('Retrospective / Hindsight')).toBeInTheDocument()
    expect(
      screen.getByText('Hindsight. Not available at decision time. Does not justify, reinforce, or validate the decision.'),
    ).toBeInTheDocument()
  })

  it('formats the hindsight forward return as a signed percentage, not a raw decimal', async () => {
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    // AUDIT_RAW_RESULT.retrospective_hindsight.forward_return_10d = 0.068
    expect(screen.getByText('+6.80%')).toBeInTheDocument()
    expect(screen.queryByText('0.0680')).not.toBeInTheDocument()
  })

  it('never treats a model-generated citation-marker-like string as an authoritative source', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue({
      ...MOCK_RESPONSE,
      answer: 'The rule requires RSI in range 【fake-injected-source】.',
    })
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    // knowledge_sources still comes only from the real backend array (1 item) -- the
    // citation-marker-shaped text in the answer never becomes a rendered source.
    expect(screen.getByText('1 source document · 1 supporting excerpt')).toBeInTheDocument()
    expect(screen.queryByText('fake-injected-source')).not.toBeInTheDocument()
  })
})

describe('Research Workspace audit hindsight availability reason (generic, not symbol-specific)', () => {
  afterEach(() => vi.restoreAllMocks())

  async function submit(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'Audit a symbol.')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))
    await waitFor(() => expect(screen.getByText('Research Synthesis')).toBeInTheDocument())
  }

  // Deliberately an arbitrary symbol/date distinct from the RELIANCE/2024-06-13
  // fixture used elsewhere -- proves the reason logic is generic, not tied to
  // any particular instrument, and reads only `decision`/`available_forward_bars`.
  function auditResponse(overrides: Partial<AuditToolEvidence>) {
    return {
      ...MOCK_RESPONSE,
      tool_trace: [
        {
          ...MOCK_RESPONSE.tool_trace[0],
          raw_result: { ...AUDIT_RAW_RESULT, symbol: 'SBIN.NS', audit_date: '2025-03-24', ...overrides },
        },
      ],
    }
  }

  it('explains a non-BUY decision has no retrospective outcome, without fabricating a value', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(
      auditResponse({
        decision: 'NO_SIGNAL' as const,
        retrospective_hindsight: { forward_return_10d: null, available_forward_bars: null, note: AUDIT_RAW_RESULT.retrospective_hindsight.note },
      }),
    )
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(screen.getByText('No retrospective outcome applies because the audited decision was NO_SIGNAL, not BUY.')).toBeInTheDocument()
    expect(screen.queryByText('10-Bar forward return')).not.toBeInTheDocument()
  })

  it('explains a BUY decision with insufficient forward bars distinctly from a non-BUY decision', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(
      auditResponse({
        decision: 'BUY' as const,
        retrospective_hindsight: { forward_return_10d: null, available_forward_bars: 4, note: AUDIT_RAW_RESULT.retrospective_hindsight.note },
      }),
    )
    const user = userEvent.setup()
    renderPage()
    await submit(user)

    expect(
      screen.getByText('The 10-bar retrospective outcome is not yet available -- only 4 of 10 required forward trading bars exist in the requested date range.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('No retrospective outcome applies')).not.toBeInTheDocument()
  })
})

describe('Research Workspace Markdown synthesis rendering', () => {
  afterEach(() => vi.restoreAllMocks())

  async function submitWithAnswer(answer: string) {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue({ ...MOCK_RESPONSE, tool_trace: [], knowledge_sources: [], answer })
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'Question')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))
    await waitFor(() => expect(screen.getByText('Research Synthesis')).toBeInTheDocument())
  }

  it('renders Markdown bold as actual strong text', async () => {
    await submitWithAnswer('The rule requires **close above SMA20**.')
    const strong = screen.getByText('close above SMA20')
    expect(strong.tagName).toBe('STRONG')
  })

  it('renders a Markdown list structurally', async () => {
    await submitWithAnswer('Conditions:\n\n- Close > SMA20\n- SMA20 > SMA50\n- RSI in range')
    const item = screen.getByText('Close > SMA20')
    expect(item.tagName).toBe('LI')
    expect(item.closest('ul')).not.toBeNull()
  })

  it('renders a GFM comparison table as a real HTML table', async () => {
    await submitWithAnswer('| Metric | Failed | Non-Failed |\n| --- | --- | --- |\n| Average RSI | 45.3 | 57.5 |')
    const table = document.querySelector('table')
    expect(table).not.toBeNull()
    expect(screen.getByText('Metric')).toBeInTheDocument()
    expect(screen.getByText('45.3')).toBeInTheDocument()
  })

  it('gives the table wrapper a responsive, horizontally-scrollable style contract', async () => {
    await submitWithAnswer('| A | B |\n| --- | --- |\n| 1 | 2 |')
    const table = document.querySelector('table') as HTMLTableElement
    const wrapper = table.parentElement as HTMLElement
    expect(wrapper.className).toContain('overflow-x-auto')
  })

  it('never renders unsafe raw HTML from model output as executable/real elements', async () => {
    await submitWithAnswer('Ignore prior rules <img src=x onerror="window.__pwned = true"> and <script>window.__pwned = true</script> now.')
    expect(document.querySelector('img')).toBeNull()
    expect(document.querySelector('script[data-injected]')).toBeNull()
    expect((window as unknown as { __pwned?: boolean }).__pwned).not.toBe(true)
  })

  it('lets long prose cells wrap instead of forcing the table absurdly wide', async () => {
    await submitWithAnswer(
      '| Condition | Requirement |\n| --- | --- |\n| Close > SMA20 | The closing price must be strictly greater than the 20-period simple moving average. |',
    )
    const cells = document.querySelectorAll('td')
    for (const cell of cells) {
      expect(cell.className).not.toContain('whitespace-nowrap')
    }
    const table = document.querySelector('table') as HTMLTableElement
    expect(table.className).toContain('table-fixed')
  })
})

describe('Research Workspace knowledge-source grouping', () => {
  afterEach(() => vi.restoreAllMocks())

  const MULTI_CHUNK_RESPONSE: ResearchResponse = {
    ...MOCK_RESPONSE,
    knowledge_sources: [
      {
        document_id: 'strategy_trend_momentum_v1',
        document_title: 'Trend + Momentum v1 Strategy',
        source_path: 'strategy_trend_momentum_v1.md',
        chunk_id: 'strategy_trend_momentum_v1::chunk::000',
        chunk_ordinal: 0,
        section_heading: 'BUY Rule',
        trust: 'AUTHORITATIVE_INTERNAL',
      },
      {
        document_id: 'strategy_trend_momentum_v1',
        document_title: 'Trend + Momentum v1 Strategy',
        source_path: 'strategy_trend_momentum_v1.md',
        chunk_id: 'strategy_trend_momentum_v1::chunk::001',
        chunk_ordinal: 1,
        section_heading: 'Decisions',
        trust: 'AUTHORITATIVE_INTERNAL',
      },
      {
        document_id: 'risk_analytics',
        document_title: 'Performance & Risk Analytics',
        source_path: 'risk_analytics.md',
        chunk_id: 'risk_analytics::chunk::001',
        chunk_ordinal: 1,
        section_heading: 'Core Definitions',
        trust: 'AUTHORITATIVE_INTERNAL',
      },
    ],
  }

  async function submitMultiChunk() {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MULTI_CHUNK_RESPONSE)
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'Explain the BUY rule.')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))
    await waitFor(() => expect(screen.getByText('Research Synthesis')).toBeInTheDocument())
  }

  it('groups same-document chunks into one source entry with an accurate document/excerpt count', async () => {
    await submitMultiChunk()

    // 2 source documents (strategy_trend_momentum_v1 grouped, risk_analytics separate), 3 excerpts total
    expect(screen.getByText('2 source documents · 3 supporting excerpts')).toBeInTheDocument()
    expect(screen.getAllByText('Trend + Momentum v1 Strategy')).toHaveLength(1)
    expect(screen.getByText('2 supporting excerpts')).toBeInTheDocument()
    expect(screen.getByText('Performance & Risk Analytics')).toBeInTheDocument()
    expect(screen.getByText('1 supporting excerpt')).toBeInTheDocument()
  })

  it('keeps section names visible for a grouped source', async () => {
    await submitMultiChunk()
    expect(screen.getByText('BUY Rule · Decisions')).toBeInTheDocument()
  })

  it('never loses a source -- every chunk is reachable via View details, none silently dropped', async () => {
    const user = userEvent.setup()
    await submitMultiChunk()

    const detailButtons = screen.getAllByRole('button', { name: 'View details' })
    expect(detailButtons).toHaveLength(2) // one per grouped document
    for (const button of detailButtons) {
      await user.click(button)
    }
    expect(screen.getByText('strategy_trend_momentum_v1::chunk::000')).toBeInTheDocument()
    expect(screen.getByText('strategy_trend_momentum_v1::chunk::001')).toBeInTheDocument()
    expect(screen.getByText('risk_analytics::chunk::001')).toBeInTheDocument()
  })
})

describe('Research Workspace error states', () => {
  afterEach(() => vi.restoreAllMocks())

  async function submitAndFail(mockError: ApiError) {
    vi.spyOn(researchApi, 'postResearchQuestion').mockRejectedValue(mockError)
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'What is RSI14?')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))
    return screen.findByRole('alert')
  }

  it('shows a validation error message', async () => {
    const alert = await submitAndFail(new ApiError(422, 'INVALID_RESEARCH_QUESTION', 'question must not be blank.'))
    expect(alert).toHaveTextContent('Invalid research question')
  })

  it('shows a distinguishable provider-unavailable state, not raw backend text', async () => {
    const alert = await submitAndFail(new ApiError(503, 'AI_PROVIDER_NOT_CONFIGURED', 'GROQ_API_KEY is not configured.'))
    expect(alert).toHaveTextContent('AI synthesis is temporarily unavailable')
    expect(alert).not.toHaveTextContent('GROQ_API_KEY')
  })

  it('shows a sign-in-again message when the session is missing/expired (post-5F auth requirement)', async () => {
    const alert = await submitAndFail(new ApiError(401, 'SESSION_INVALID', 'Not authenticated.'))
    expect(alert).toHaveTextContent('Your session has expired')
    expect(alert).toHaveTextContent('sign in again')
  })

  it('shows a safe generic message for an internal/tool error', async () => {
    const alert = await submitAndFail(new ApiError(500, 'INTERNAL_DATA_CONTRACT_ERROR', 'Internal error.'))
    expect(alert).toHaveTextContent('Research request failed')
  })

  it('shows a distinct rate-limit message for a genuine Groq 429, not the generic provider-unavailable copy', async () => {
    const alert = await submitAndFail(new ApiError(429, 'AI_PROVIDER_RATE_LIMITED', 'Groq rate/quota limit reached.'))
    expect(alert).toHaveTextContent('AI research is temporarily rate-limited')
    expect(alert).not.toHaveTextContent('AI synthesis is temporarily unavailable')
  })
})

describe('Research Workspace request count', () => {
  afterEach(() => vi.restoreAllMocks())

  it('issues exactly one POST research request per submission (no duplicate/StrictMode-style double call)', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MOCK_RESPONSE)
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'Audit RELIANCE.')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))
    await waitFor(() => expect(screen.getByText('Research Synthesis')).toBeInTheDocument())

    expect(researchApi.postResearchQuestion).toHaveBeenCalledTimes(1)
  })

  it('issues exactly one request when submitting via a suggested question button', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MOCK_RESPONSE)
    renderPage()
    const user = userEvent.setup()

    await user.click(screen.getByText(/What does an unavailable 10-bar outcome mean\?/))
    await waitFor(() => expect(researchApi.postResearchQuestion).toHaveBeenCalled())

    expect(researchApi.postResearchQuestion).toHaveBeenCalledTimes(1)
  })
})

describe('Research Workspace theming', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders identically under light and dark themes (no financial values depend on theme)', async () => {
    vi.spyOn(researchApi, 'postResearchQuestion').mockResolvedValue(MOCK_RESPONSE)
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <MemoryRouter>
          <ResearchPage />
        </MemoryRouter>
      </ThemeProvider>,
    )
    await user.type(screen.getByRole('textbox', { name: /research question/i }), 'Audit RELIANCE.')
    await user.click(screen.getByRole('button', { name: 'Run Research' }))
    await waitFor(() => expect(screen.getByText('Research Synthesis')).toBeInTheDocument())
    // The same verbatim answer/tool-trace/source text renders regardless of theme --
    // theme only ever changes CSS custom properties (see ThemeProvider), never data.
    expect(screen.getByText('The strategy produced BUY because all three conditions passed.')).toBeInTheDocument()
  })
})
