// Mirrors backend/app/api/schemas/*.py exactly. Do not reinterpret field
// names or add fields not present in the API contract.

export interface Instrument {
  symbol: string
  exchange: string
  name: string
  provider_symbol: string
  instrument_type: string
  status: string
  isin: string | null
  series: string | null
}

export interface InstrumentSearchResponse {
  results: Instrument[]
}

export interface OHLCVBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  adj_close: number | null
  volume: number
}

export interface MarketDataResponse {
  provider_symbol: string
  interval: string
  bars: OHLCVBar[]
}

export interface IndicatorRow {
  date: string
  sma20: number | null
  sma50: number | null
  rsi14: number | null
  average_volume: number | null
  volume_ratio: number | null
}

export interface IndicatorResponse {
  provider_symbol: string
  interval: string
  rows: IndicatorRow[]
}

export interface NamedValue {
  name: string
  value: number
}

// Preserve exactly: BUY / NO_SIGNAL / INSUFFICIENT_DATA. Never remap to
// HOLD / SELL / "Strong Buy" / confidence scores anywhere in the UI.
export type StrategyDecision = 'BUY' | 'NO_SIGNAL' | 'INSUFFICIENT_DATA'

export interface ConditionResult {
  condition_id: string
  description: string
  passed: boolean
  actual_values: NamedValue[]
  operator: string
  reference_values: NamedValue[]
}

export interface StrategyEvaluation {
  date: string
  strategy_id: string
  strategy_name: string
  decision: StrategyDecision
  conditions: ConditionResult[]
  missing_inputs: string[]
}

export interface StrategyEvaluationSeriesResponse {
  provider_symbol: string
  interval: string
  strategy_id: string
  strategy_name: string
  evaluations: StrategyEvaluation[]
}

// Phase 2A — historical BUY-signal outcome research. `reference_close` is
// observational (the same raw Close Phase 1D already evaluated), never an
// execution fill — never render or label it as "Entry Price".
export interface SignalOutcome {
  date: string
  decision: StrategyDecision
  reference_close: number
  forward_close_5d: number | null
  forward_return_5d: number | null
  forward_close_10d: number | null
  forward_return_10d: number | null
  mae_10d: number | null
  mfe_10d: number | null
  available_forward_bars: number
}

export interface SignalOutcomeSeriesResponse {
  provider_symbol: string
  interval: string
  strategy_id: string
  strategy_name: string
  outcomes: SignalOutcome[]
}

// Phase 2B — executable backtest under the frozen V1 execution rules.
export interface BacktestConfig {
  initial_capital: number
  transaction_cost: number
  slippage: number
}

export interface ExecutedTrade {
  entry_signal_date: string
  entry_date: string
  entry_price: number
  exit_signal_date: string
  exit_date: string
  exit_price: number
  quantity: number
  gross_pnl: number
  gross_return: number
  net_pnl: number
}

export interface OpenPosition {
  entry_signal_date: string
  entry_date: string
  entry_price: number
  quantity: number
  pending_exit_signal_date: string | null
}

export interface EquityPoint {
  date: string
  cash: number
  position_quantity: number
  position_market_value: number
  equity: number
}

export interface BacktestResultResponse {
  provider_symbol: string
  interval: string
  strategy_id: string
  strategy_name: string
  config: BacktestConfig
  trades: ExecutedTrade[]
  open_position: OpenPosition | null
  pending_entry_signal_date: string | null
  equity_curve: EquityPoint[]
}

// Phase 2C — performance/risk analytics over a completed backtest.
export interface DrawdownPoint {
  date: string
  equity: number
  running_peak: number
  drawdown: number
}

export interface PerformanceAnalyticsResponse {
  provider_symbol: string
  interval: string
  strategy_id: string
  strategy_name: string

  initial_equity: number
  ending_equity: number
  total_return: number

  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number

  closed_trade_count: number
  winner_count: number
  loser_count: number
  breakeven_count: number
  win_rate: number | null

  average_trade_return: number | null
  median_trade_return: number | null
  best_trade_return: number | null
  worst_trade_return: number | null

  peak_equity: number

  maximum_drawdown: number
  max_drawdown_peak_date: string
  max_drawdown_trough_date: string

  exposed_bar_count: number
  total_bar_count: number
  exposure: number | null

  drawdown_series: DrawdownPoint[]
}

// Phase 3A/3B/3C/3D — point-in-time Strategy Auditor. Frozen terminology:
// "Prior Strategy Signals" (never "similar"/"matching"/"comparable" — V1
// has no similarity/regime matching). Do not recompute any of these values;
// render exactly what the API returns, formatted for display only.
export interface AuditHorizonStatistics {
  eligible_outcome_count: number
  positive_count: number
  negative_count: number
  breakeven_count: number
  hit_rate: number | null
  average_return: number | null
}

export interface HistoricalSignalEvidence {
  prior_signal_count: number
  five_bar: AuditHorizonStatistics
  ten_bar: AuditHorizonStatistics
}

export interface HistoricalSignalRisk {
  eligible_outcome_count: number
  average_mae_10d: number | null
  worst_mae_10d: number | null
  average_mfe_10d: number | null
  best_mfe_10d: number | null
}

export type Comparison = 'ABOVE' | 'BELOW' | 'EQUAL'

export interface RegimeEvidence {
  close: number | null
  sma20: number | null
  sma50: number | null
  close_vs_sma20: Comparison | null
  sma20_vs_sma50: Comparison | null
}

// Preserve exactly: BULLISH_TREND / BEARISH_TREND / TRANSITIONAL /
// INSUFFICIENT_DATA. Never invent regime descriptions or predictions.
export type MarketRegime = 'BULLISH_TREND' | 'BEARISH_TREND' | 'TRANSITIONAL' | 'INSUFFICIENT_DATA'

export interface RiskMarketContext {
  annualized_realized_volatility_20: number | null
  regime: MarketRegime
  regime_evidence: RegimeEvidence
}

export interface StrategyAuditResponse {
  provider_symbol: string
  interval: string
  strategy_id: string
  strategy_name: string
  audit_date: string
  evaluation: StrategyEvaluation
  historical_evidence: HistoricalSignalEvidence
  historical_signal_risk: HistoricalSignalRisk
  risk_market_context: RiskMarketContext
  // Hindsight-only — present only for a BUY audit_date, null for
  // NO_SIGNAL/INSUFFICIENT_DATA. Must stay visually/structurally separate
  // from every point-in-time section above.
  retrospective_outcome: SignalOutcome | null
}

// Phase 4A-4E — Strategy Failure Investigator. Frozen v1 classification:
// FAILED = NEGATIVE (accepted 10-trading-bar forward return strictly
// negative); NON_FAILED = POSITIVE or BREAKEVEN; UNAVAILABLE = incomplete
// 10-bar outcome (excluded from FAILED/NON_FAILED comparisons, never
// interpreted as failure). Never reinterpret these values or invent a
// return-loss threshold in the frontend.
export type SignalInvestigationClassification = 'POSITIVE' | 'NEGATIVE' | 'BREAKEVEN' | 'UNAVAILABLE'

// Phase 4B: descriptive-only outcome summary for one population (FAILED or
// NON_FAILED). All fields are decimal fractions from the backend, signed,
// never rounded/abs()'d/multiplied by 100 here.
export interface PopulationSummary {
  count: number
  average_forward_return_10d: number | null
  median_forward_return_10d: number | null
  average_mae_10d: number | null
  median_mae_10d: number | null
  worst_mae_10d: number | null
  average_mfe_10d: number | null
  median_mfe_10d: number | null
  best_mfe_10d: number | null
}

export interface FailurePopulationComparison {
  failed: PopulationSummary
  non_failed: PopulationSummary
}

// Phase 4C: descriptive-only signal-time (point-in-time) context summary
// for one population.
export interface SignalContextSummary {
  count: number
  average_rsi14: number | null
  median_rsi14: number | null
  volatility_available_count: number
  volatility_unavailable_count: number
  average_annualized_realized_volatility_20: number | null
  median_annualized_realized_volatility_20: number | null
  average_close_above_sma20_fraction: number | null
  median_close_above_sma20_fraction: number | null
  average_sma20_above_sma50_fraction: number | null
  median_sma20_above_sma50_fraction: number | null
  bullish_trend_count: number
  bearish_trend_count: number
  transitional_count: number
  insufficient_data_count: number
}

// One historical BUY signal's signal-time context (Phase 4C). `close`/
// `sma20`/`sma50`/`rsi14`/both trend-distance fractions are always present
// (a valid historical BUY structurally requires them); only
// `annualized_realized_volatility_20` may legitimately be null (fewer than
// 21 closes of history).
export interface SignalFailureContext {
  signal_date: string
  classification: SignalInvestigationClassification
  regime: MarketRegime
  annualized_realized_volatility_20: number | null
  rsi14: number
  close: number
  sma20: number
  sma50: number
  close_above_sma20_fraction: number
  sma20_above_sma50_fraction: number
}

export interface FailureContextAnalysis {
  failed: SignalContextSummary
  non_failed: SignalContextSummary
  // Chronological/source order exactly as the backend returns it — never
  // re-sort, group by classification, or filter this array itself; UI-only
  // filtering must operate on a derived view, not mutate this list.
  observations: SignalFailureContext[]
}

export interface StrategyFailureInvestigationResponse {
  provider_symbol: string
  interval: string
  strategy_id: string
  strategy_name: string

  total_signal_count: number
  eligible_count: number
  failed_count: number
  non_failed_count: number
  unavailable_count: number

  // Retrospective (post-signal) outcome comparison — kept structurally
  // distinct from context_analysis below.
  outcome_comparison: FailurePopulationComparison
  // Signal-time (point-in-time) context comparison.
  context_analysis: FailureContextAnalysis
}

export interface HealthResponse {
  status: string
  service: string
  version: string
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
  }
}

// Phase 5E — AI Research Workspace, over the accepted Phase 5C tool-using
// research agent. The UI never recomputes anything below; every field is
// rendered verbatim from the backend response (see utils/format.ts for
// the only allowed presentation-only transforms).

export interface ResearchRequest {
  question: string
}

export type ResearchToolStatus = 'ok' | 'error' | 'rejected'
export type ResearchStoppedReason = 'final_answer' | 'max_steps_reached' | 'insufficient_evidence'

export interface ToolTraceEntry {
  tool_name: string
  status: ResearchToolStatus
  arguments: Record<string, unknown>
  result_summary: string
  // Full normalized tool result (Phase 5E, additive) -- present only for
  // status "ok". Shape varies per tool; see AuditToolEvidence below for
  // audit_strategy_decision's specific, accepted 4-part structure.
  raw_result: Record<string, unknown> | null
}

export interface KnowledgeSource {
  document_id: string
  document_title: string
  source_path: string
  chunk_id: string
  chunk_ordinal: number
  section_heading: string | null
  trust: string
}

export interface ResearchResponse {
  question: string
  answer: string
  stopped_reason: ResearchStoppedReason
  completed_steps: number
  tool_trace: ToolTraceEntry[]
  knowledge_sources: KnowledgeSource[]
  model: string | null
}

// The accepted audit_strategy_decision tool result shape (see CLAUDE.md
// Phase 5C final hardening) -- used only to narrow a ToolTraceEntry's
// generic `raw_result` when tool_name === 'audit_strategy_decision', so
// the UI can keep decision evidence / point-in-time context /
// retrospective hindsight visually and structurally separate. Never
// derived from other tools' output.
export interface AuditDecisionEvidenceCondition {
  condition_id: string
  description: string
  passed: boolean
  operator: string
  actual_values: NamedValue[]
  reference_values: NamedValue[]
}

export interface AuditPointInTimeContext {
  prior_signal_count: number
  five_bar_hit_rate: number | null
  five_bar_average_return: number | null
  ten_bar_hit_rate: number | null
  ten_bar_average_return: number | null
  regime: MarketRegime
  annualized_realized_volatility_20: number | null
}

export interface AuditRetrospectiveHindsight {
  forward_return_10d: number | null
  // Phase 2A's own field, passed through verbatim. null exactly when the
  // audited decision was not BUY (no retrospective outcome exists at
  // all); a number less than 10 when the decision WAS BUY but fewer than
  // 10 forward trading bars exist yet in the requested range.
  available_forward_bars: number | null
  note: string
}

export interface AuditToolEvidence {
  symbol: string
  audit_date: string
  decision: StrategyDecision
  decision_evidence: AuditDecisionEvidenceCondition[]
  missing_inputs: string[]
  point_in_time_context: AuditPointInTimeContext
  retrospective_hindsight: AuditRetrospectiveHindsight
}

export type AuthProvider = 'LOCAL' | 'GOOGLE'

export interface AuthUser {
  id: string
  email: string
  full_name: string
  display_name: string
  avatar_url: string | null
  auth_provider: AuthProvider
}
