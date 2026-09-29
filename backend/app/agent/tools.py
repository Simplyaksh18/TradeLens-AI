"""Phase 5C: thin, application-owned tool wrappers around EXISTING
accepted TradeLens domain/service functions. No financial calculation is
duplicated or reimplemented here -- every number a tool returns comes
from the same accepted engines the REST API already uses (see
app.api.research, app.api.routes.audits, app.api.routes.investigations).

Every handler has the signature `(arguments: dict, deps: AgentDependencies)
-> ToolResult` and NEVER raises -- malformed input, an unknown symbol, a
domain input-contract violation, or any other failure is always caught
and returned as `ToolResult(status="error", ...)` so a single bad tool
call can never crash the agent loop or leak a raw traceback.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta
from typing import Any

from app.agent.dependencies import AgentDependencies
from app.agent.models import ToolDefinition, ToolResult
from app.api.dependencies import HistoryQueryParams, backtest_query_params, history_query_params
from app.api.errors import RequestContractError
from app.api.research import build_strategy_research
from app.api.routes.audits import CALCULATION_WARMUP_CALENDAR_DAYS
from app.audit.engine import build_strategy_audit
from app.backtesting.engine import run_backtest as run_backtest_engine
from app.backtesting.models import BacktestConfig
from app.analytics.engine import compute_performance_analytics
from app.core.exceptions import KnowledgeError, MarketDataError
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.composer import build_strategy_failure_investigation
from app.investigation.context import build_failure_context_dataset
from app.investigation.engine import build_signal_investigation_dataset
from app.outcomes.engine import compute_signal_outcomes

_CONTROLLED_ERRORS = (MarketDataError, KnowledgeError, RequestContractError)


def _error(code: str, message: str) -> ToolResult:
    return ToolResult(status="error", error_code=code, error_message=message)


def _parse_date(value: Any, field_name: str) -> Date:
    if isinstance(value, Date):
        return value
    if not isinstance(value, str):
        raise RequestContractError("INVALID_ARGUMENT", f"{field_name!r} must be a YYYY-MM-DD date string.")
    try:
        return Date.fromisoformat(value)
    except ValueError as exc:
        raise RequestContractError("INVALID_ARGUMENT", f"{field_name!r} is not a valid YYYY-MM-DD date: {exc}") from exc


def _require_str(arguments: dict, name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RequestContractError("INVALID_ARGUMENT", f"{name!r} must be a non-blank string.")
    return value.strip()


def _history_params(arguments: dict) -> HistoryQueryParams:
    start = _parse_date(_require_str(arguments, "start"), "start")
    end = _parse_date(_require_str(arguments, "end"), "end")
    interval = arguments.get("interval", "1d")
    if not isinstance(interval, str):
        raise RequestContractError("INVALID_ARGUMENT", "'interval' must be a string.")
    return history_query_params(start=start, end=end, interval=interval)  # reuses accepted validation


def _run(handler_body, arguments: dict, deps: AgentDependencies) -> ToolResult:
    try:
        return handler_body(arguments, deps)
    except _CONTROLLED_ERRORS as exc:
        code = getattr(exc, "code", exc.__class__.__name__)
        message = getattr(exc, "message", str(exc)) or str(exc)
        return _error(code, message)
    except Exception as exc:  # last-resort containment -- a tool must never crash the agent loop
        return _error("TOOL_EXECUTION_FAILED", f"{exc.__class__.__name__}: {exc}")


# ---------------------------------------------------------------------------
# 1. search_instruments
# ---------------------------------------------------------------------------


def _search_instruments(arguments: dict, deps: AgentDependencies) -> ToolResult:
    query = _require_str(arguments, "query")
    limit = arguments.get("limit", 20)
    if not isinstance(limit, int) or not (1 <= limit <= 100):
        raise RequestContractError("INVALID_ARGUMENT", "'limit' must be an integer between 1 and 100.")
    results = deps.instrument_master.search(query, limit=limit)
    return ToolResult(
        status="ok",
        data={
            "results": [
                {"symbol": i.symbol, "name": i.name, "exchange": i.exchange.value, "provider_symbol": i.provider_symbol}
                for i in results
            ]
        },
    )


def search_instruments(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_search_instruments, arguments, deps)


# ---------------------------------------------------------------------------
# 2. get_strategy_evaluation
# ---------------------------------------------------------------------------


def _get_strategy_evaluation(arguments: dict, deps: AgentDependencies) -> ToolResult:
    symbol = _require_str(arguments, "symbol")
    params = _history_params(arguments)
    market_series, _, evaluation_series = build_strategy_research(symbol, params, deps.market_data_service)

    target_date_raw = arguments.get("target_date")
    target_date = _parse_date(target_date_raw, "target_date") if target_date_raw else evaluation_series.evaluations[-1].date

    target = next((e for e in evaluation_series.evaluations if e.date == target_date), None)
    if target is None:
        raise RequestContractError("TARGET_DATE_NOT_A_TRADING_BAR", f"No evaluation exists for {target_date} in the requested range.")

    decisions = [e.decision.value for e in evaluation_series.evaluations]
    return ToolResult(
        status="ok",
        data={
            "symbol": market_series.provider_symbol,
            "interval": evaluation_series.interval,
            "target_date": target_date.isoformat(),
            "decision": target.decision.value,
            "conditions": [
                {
                    "condition_id": c.condition_id,
                    "description": c.description,
                    "passed": c.passed,
                    "operator": c.operator,
                    "actual_values": [{"name": v.name, "value": v.value} for v in c.actual_values],
                    "reference_values": [{"name": v.name, "value": v.value} for v in c.reference_values],
                }
                for c in target.conditions
            ],
            "missing_inputs": list(target.missing_inputs),
            "range_summary": {
                "total": len(decisions),
                "buy_count": decisions.count("BUY"),
                "no_signal_count": decisions.count("NO_SIGNAL"),
                "insufficient_data_count": decisions.count("INSUFFICIENT_DATA"),
            },
        },
    )


def get_strategy_evaluation(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_get_strategy_evaluation, arguments, deps)


# ---------------------------------------------------------------------------
# 3. get_signal_outcomes
# ---------------------------------------------------------------------------


def _get_signal_outcomes(arguments: dict, deps: AgentDependencies) -> ToolResult:
    symbol = _require_str(arguments, "symbol")
    params = _history_params(arguments)
    market_series, _, evaluation_series = build_strategy_research(symbol, params, deps.market_data_service)
    outcome_series = compute_signal_outcomes(market_series, evaluation_series)

    return ToolResult(
        status="ok",
        data={
            "symbol": outcome_series.provider_symbol,
            "interval": outcome_series.interval,
            "count": len(outcome_series.outcomes),
            "outcomes": [
                {
                    "signal_date": o.date.isoformat(),
                    "reference_close": o.reference_close,
                    "forward_return_5d": o.forward_return_5d,
                    "forward_return_10d": o.forward_return_10d,
                    "mae_10d": o.mae_10d,
                    "mfe_10d": o.mfe_10d,
                    "available_forward_bars": o.available_forward_bars,
                }
                for o in outcome_series.outcomes
            ],
        },
    )


def get_signal_outcomes(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_get_signal_outcomes, arguments, deps)


# ---------------------------------------------------------------------------
# 4. run_backtest
# ---------------------------------------------------------------------------


def _run_backtest(arguments: dict, deps: AgentDependencies) -> ToolResult:
    symbol = _require_str(arguments, "symbol")
    params = _history_params(arguments)
    initial_capital = arguments.get("initial_capital", 100_000.0)
    if not isinstance(initial_capital, (int, float)):
        raise RequestContractError("INVALID_ARGUMENT", "'initial_capital' must be a number.")
    capital_params = backtest_query_params(initial_capital=float(initial_capital))  # reuses accepted validation

    market_series, _, evaluation_series = build_strategy_research(symbol, params, deps.market_data_service)
    result = run_backtest_engine(market_series, evaluation_series, BacktestConfig(initial_capital=capital_params.initial_capital))

    return ToolResult(
        status="ok",
        data={
            "symbol": market_series.provider_symbol,
            "initial_capital": capital_params.initial_capital,
            "closed_trade_count": len(result.trades),
            "trades": [
                {
                    "entry_date": t.entry_date.isoformat() if t.entry_date else None,
                    "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "gross_pnl": t.gross_pnl,
                    "net_pnl": t.net_pnl,
                    "gross_return": t.gross_return,
                }
                for t in result.trades
            ],
            "open_position": (
                None
                if result.open_position is None
                else {
                    "entry_date": result.open_position.entry_date.isoformat(),
                    "entry_price": result.open_position.entry_price,
                    "quantity": result.open_position.quantity,
                }
            ),
            "starting_equity": result.equity_curve[0].equity if result.equity_curve else None,
            "ending_equity": result.equity_curve[-1].equity if result.equity_curve else None,
            "equity_points_count": len(result.equity_curve),
        },
    )


def run_backtest(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_run_backtest, arguments, deps)


# ---------------------------------------------------------------------------
# 5. get_performance_analytics
# ---------------------------------------------------------------------------


def _get_performance_analytics(arguments: dict, deps: AgentDependencies) -> ToolResult:
    symbol = _require_str(arguments, "symbol")
    params = _history_params(arguments)
    initial_capital = arguments.get("initial_capital", 100_000.0)
    if not isinstance(initial_capital, (int, float)):
        raise RequestContractError("INVALID_ARGUMENT", "'initial_capital' must be a number.")
    capital_params = backtest_query_params(initial_capital=float(initial_capital))

    market_series, _, evaluation_series = build_strategy_research(symbol, params, deps.market_data_service)
    backtest_result = run_backtest_engine(market_series, evaluation_series, BacktestConfig(initial_capital=capital_params.initial_capital))
    analytics = compute_performance_analytics(backtest_result)

    return ToolResult(
        status="ok",
        data={
            "symbol": market_series.provider_symbol,
            "total_return": analytics.total_return,
            "total_pnl": analytics.total_pnl,
            "realized_pnl": analytics.realized_pnl,
            "unrealized_pnl": analytics.unrealized_pnl,
            "closed_trade_count": analytics.closed_trade_count,
            "winner_count": analytics.winner_count,
            "loser_count": analytics.loser_count,
            "breakeven_count": analytics.breakeven_count,
            "win_rate": analytics.win_rate,
            "average_trade_return": analytics.average_trade_return,
            "median_trade_return": analytics.median_trade_return,
            "best_trade_return": analytics.best_trade_return,
            "worst_trade_return": analytics.worst_trade_return,
            "maximum_drawdown": analytics.maximum_drawdown,
            "exposure": analytics.exposure,
        },
    )


def get_performance_analytics(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_get_performance_analytics, arguments, deps)


# ---------------------------------------------------------------------------
# 6. audit_strategy_decision
# ---------------------------------------------------------------------------


def _audit_strategy_decision(arguments: dict, deps: AgentDependencies) -> ToolResult:
    symbol = _require_str(arguments, "symbol")
    params = _history_params(arguments)
    audit_date = _parse_date(_require_str(arguments, "audit_date"), "audit_date")

    calc_start = min(params.start, audit_date - timedelta(days=CALCULATION_WARMUP_CALENDAR_DAYS))
    calc_params = HistoryQueryParams(start=calc_start, end=params.end, interval=params.interval)
    market_series, indicator_series, evaluation_series = build_strategy_research(symbol, calc_params, deps.market_data_service)

    if not any(bar.date == audit_date for bar in market_series.bars):
        raise RequestContractError("AUDIT_DATE_NOT_A_TRADING_BAR", f"No trading bar exists for audit_date {audit_date}.")

    outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    audit = build_strategy_audit(
        market_series, evaluation_series, outcome_series, indicator_series, audit_date, evidence_start_date=params.start
    )

    retro = audit.retrospective_outcome
    return ToolResult(
        status="ok",
        data={
            "symbol": market_series.provider_symbol,
            "audit_date": audit_date.isoformat(),
            # AUTHORITATIVE: the decision is the deterministic output of
            # the accepted Trend + Momentum v1 rule, evaluated from
            # decision_evidence below -- nothing else determines it.
            "decision": audit.evaluation.decision.value,
            "decision_evidence": [
                {
                    "condition_id": c.condition_id,
                    "description": c.description,
                    "passed": c.passed,
                    "operator": c.operator,
                    "actual_values": [{"name": v.name, "value": v.value} for v in c.actual_values],
                    "reference_values": [{"name": v.name, "value": v.value} for v in c.reference_values],
                }
                for c in audit.evaluation.conditions
            ],
            "missing_inputs": list(audit.evaluation.missing_inputs),
            # POINT-IN-TIME CONTEXT ONLY: descriptive evidence about the
            # situation surrounding the decision above. None of these
            # fields are inputs to, or justification for, the decision --
            # the decision was already fully determined by
            # decision_evidence before this context is even computed.
            "point_in_time_context": {
                "prior_signal_count": audit.historical_evidence.prior_signal_count,
                "five_bar_hit_rate": audit.historical_evidence.five_bar.hit_rate,
                "five_bar_average_return": audit.historical_evidence.five_bar.average_return,
                "ten_bar_hit_rate": audit.historical_evidence.ten_bar.hit_rate,
                "ten_bar_average_return": audit.historical_evidence.ten_bar.average_return,
                "regime": audit.risk_market_context.regime.value,
                "annualized_realized_volatility_20": audit.risk_market_context.annualized_realized_volatility_20,
            },
            # HINDSIGHT ONLY: not knowable at audit_date. Never a
            # justification, reinforcement, or validation of the decision
            # above -- shown for retrospective research only.
            #
            # `available_forward_bars` is Phase 2A's own already-computed
            # field, passed through verbatim (never a new calculation) so a
            # caller can distinguish WHY forward_return_10d is null: either
            # the audited decision was not BUY (retro is None, so this is
            # also None), or it was BUY but fewer than 10 forward trading
            # bars exist yet within the requested range (retro is present,
            # forward_return_10d is None, available_forward_bars < 10).
            "retrospective_hindsight": {
                "forward_return_10d": retro.forward_return_10d if retro else None,
                "available_forward_bars": retro.available_forward_bars if retro else None,
                "note": "Hindsight. Not available at decision time. Does not justify, reinforce, or validate the decision.",
            },
        },
    )


def audit_strategy_decision(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_audit_strategy_decision, arguments, deps)


# ---------------------------------------------------------------------------
# 7. investigate_strategy_failures
# ---------------------------------------------------------------------------


def _investigate_strategy_failures(arguments: dict, deps: AgentDependencies) -> ToolResult:
    symbol = _require_str(arguments, "symbol")
    params = _history_params(arguments)

    calc_start = params.start - timedelta(days=CALCULATION_WARMUP_CALENDAR_DAYS)
    calc_params = HistoryQueryParams(start=calc_start, end=params.end, interval=params.interval)
    market_series, indicator_series, evaluation_series = build_strategy_research(symbol, calc_params, deps.market_data_service)

    full_outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    windowed_outcomes = tuple(o for o in full_outcome_series.outcomes if params.start <= o.date <= params.end)
    from app.outcomes.models import SignalOutcomeSeries

    outcome_series = SignalOutcomeSeries(
        provider_symbol=full_outcome_series.provider_symbol,
        interval=full_outcome_series.interval,
        strategy_id=full_outcome_series.strategy_id,
        strategy_name=full_outcome_series.strategy_name,
        outcomes=windowed_outcomes,
    )

    dataset = build_signal_investigation_dataset(outcome_series)
    comparison = build_failure_population_comparison(dataset)
    context = build_failure_context_dataset(dataset, market_series, indicator_series)
    investigation = build_strategy_failure_investigation(dataset, comparison, context)

    return ToolResult(
        status="ok",
        data={
            "symbol": investigation.provider_symbol,
            "total_signal_count": investigation.total_signal_count,
            "eligible_count": investigation.eligible_count,
            "failed_count": investigation.failed_count,
            "non_failed_count": investigation.non_failed_count,
            "unavailable_count": investigation.unavailable_count,
            "failed_average_return": investigation.outcome_comparison.failed.average_forward_return_10d,
            "non_failed_average_return": investigation.outcome_comparison.non_failed.average_forward_return_10d,
            "failed_worst_mae": investigation.outcome_comparison.failed.worst_mae_10d,
            "non_failed_best_mfe": investigation.outcome_comparison.non_failed.best_mfe_10d,
            "failed_average_rsi14": investigation.context_analysis.failed.average_rsi14,
            "non_failed_average_rsi14": investigation.context_analysis.non_failed.average_rsi14,
            "note": "Per-signal observations omitted from tool output for size; these population-level comparison summaries are authoritative.",
        },
    )


def investigate_strategy_failures(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_investigate_strategy_failures, arguments, deps)


# ---------------------------------------------------------------------------
# 8. search_research_knowledge
# ---------------------------------------------------------------------------


def _search_research_knowledge(arguments: dict, deps: AgentDependencies) -> ToolResult:
    query = _require_str(arguments, "query")
    top_k = arguments.get("top_k", 5)
    if not isinstance(top_k, int) or top_k < 1:
        raise RequestContractError("INVALID_ARGUMENT", "'top_k' must be a positive integer.")

    results = deps.knowledge_retriever.retrieve(query, top_k=top_k)
    return ToolResult(
        status="ok",
        data={
            "results": [
                {
                    "chunk_id": r.chunk.source.chunk_id,
                    "chunk_ordinal": r.chunk.source.chunk_ordinal,
                    "document_id": r.chunk.source.document_id,
                    "document_title": r.chunk.source.document_title,
                    "source_path": r.chunk.source.source_path,
                    "section_heading": r.chunk.source.section_heading,
                    "trust": r.chunk.source.trust.value,
                    "score": r.score,
                    "content": r.chunk.content,
                }
                for r in results
            ]
        },
    )


def search_research_knowledge(arguments: dict, deps: AgentDependencies) -> ToolResult:
    return _run(_search_research_knowledge, arguments, deps)


# ---------------------------------------------------------------------------
# Tool definitions (JSON-schema parameters -- provider-agnostic)
# ---------------------------------------------------------------------------

_DATE_DESC = "YYYY-MM-DD"

TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="search_instruments",
        description="Search the local NSE instrument master by symbol or company name substring.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Case-insensitive substring of symbol or company name."},
                "limit": {"type": "integer", "description": "Max results (1-100, default 20)."},
            },
            "required": ["query"],
        },
        handler=search_instruments,
    ),
    ToolDefinition(
        name="get_strategy_evaluation",
        description="Get the accepted Trend + Momentum v1 decision and condition evidence for a symbol on a target date (default: latest date in range), plus BUY/NO_SIGNAL/INSUFFICIENT_DATA counts across the range.",
        parameters_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "start": {"type": "string", "description": _DATE_DESC},
                "end": {"type": "string", "description": _DATE_DESC},
                "interval": {"type": "string", "description": "Only '1d' is supported."},
                "target_date": {"type": "string", "description": f"Optional, {_DATE_DESC}. Defaults to the last date in range."},
            },
            "required": ["symbol", "start", "end"],
        },
        handler=get_strategy_evaluation,
    ),
    ToolDefinition(
        name="get_signal_outcomes",
        description="Get accepted Phase 2A historical signal outcomes (5-bar/10-bar forward return, MAE, MFE) for every historical BUY signal in the range.",
        parameters_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "start": {"type": "string", "description": _DATE_DESC},
                "end": {"type": "string", "description": _DATE_DESC},
                "interval": {"type": "string"},
            },
            "required": ["symbol", "start", "end"],
        },
        handler=get_signal_outcomes,
    ),
    ToolDefinition(
        name="run_backtest",
        description=(
            "Run the accepted Phase 2B deterministic backtest for a symbol/range/initial_capital. "
            "Returns EXECUTION evidence only: individual closed trades, the open position (if any), "
            "and starting/ending equity (not the full daily equity curve). Does NOT return win rate, "
            "total return, drawdown, exposure, or any other derived performance/risk statistic -- "
            "for those, call get_performance_analytics. Never compute a summary metric yourself from "
            "this tool's trade list."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "start": {"type": "string", "description": _DATE_DESC},
                "end": {"type": "string", "description": _DATE_DESC},
                "interval": {"type": "string"},
                "initial_capital": {"type": "number", "description": "Default 100000.0."},
            },
            "required": ["symbol", "start", "end"],
        },
        handler=run_backtest,
    ),
    ToolDefinition(
        name="get_performance_analytics",
        description=(
            "Run the accepted Phase 2B backtest then Phase 2C performance/risk analytics for a "
            "symbol/range/initial_capital. This is the ONLY authoritative source for derived "
            "performance/risk metrics: total_return, win_rate, average/median/best/worst_trade_return, "
            "maximum_drawdown, exposure, realized/unrealized P&L, winner/loser/breakeven counts. "
            "ALWAYS call this tool (never run_backtest alone) when a question asks about performance, "
            "win rate, total return, drawdown, exposure, or a trade-return summary. "
            "'exposure' is the fraction of evaluated trading bars/time during which the strategy held "
            "an open position (time-in-market) -- it is NEVER a percentage of capital allocated, an "
            "average portfolio allocation, or a position size; do not describe it that way."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "start": {"type": "string", "description": _DATE_DESC},
                "end": {"type": "string", "description": _DATE_DESC},
                "interval": {"type": "string"},
                "initial_capital": {"type": "number"},
            },
            "required": ["symbol", "start", "end"],
        },
        handler=get_performance_analytics,
    ),
    ToolDefinition(
        name="audit_strategy_decision",
        description=(
            "Run the accepted Phase 3 point-in-time Strategy Auditor for one symbol/audit_date. Returns four "
            "SEPARATE, non-interchangeable parts: (1) 'decision' -- the deterministic Trend + Momentum v1 output "
            "(BUY/NO_SIGNAL/INSUFFICIENT_DATA), determined ONLY by 'decision_evidence' (the three accepted strategy "
            "conditions: close>SMA20, SMA20>SMA50, 40<=RSI14<=70); (2) 'decision_evidence' -- the actual condition "
            "results that produced the decision; (3) 'point_in_time_context' -- prior-signal hit rates/returns, "
            "market regime, and realized volatility. This is DESCRIPTIVE CONTEXT ONLY: it does NOT determine, "
            "justify, produce, or explain WHY the decision occurred -- the decision was already fully determined by "
            "decision_evidence alone before this context is even computed; (4) 'retrospective_hindsight' -- the "
            "forward return after audit_date, which was NOT knowable at decision time and must NEVER be described "
            "as justifying, reinforcing, validating, confirming, or supporting the decision. "
            "'retrospective_hindsight.forward_return_10d' is null in exactly two distinct situations, distinguishable "
            "via 'decision' and 'available_forward_bars': (a) the audited decision was not BUY, in which case no "
            "retrospective outcome exists at all and 'available_forward_bars' is also null -- state plainly that no "
            "retrospective outcome applies because the decision was not BUY; (b) the decision WAS BUY but fewer than "
            "10 forward trading bars exist yet within the requested date range, in which case 'available_forward_bars' "
            "is a number less than 10 -- state plainly that the 10-bar outcome is not yet available because "
            "insufficient forward trading history exists in the requested range. Never conflate these two cases."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "audit_date": {"type": "string", "description": _DATE_DESC},
                "start": {"type": "string", "description": f"{_DATE_DESC}. Lower bound of the prior-signal evidence population."},
                "end": {"type": "string", "description": _DATE_DESC},
                "interval": {"type": "string"},
            },
            "required": ["symbol", "audit_date", "start", "end"],
        },
        handler=audit_strategy_decision,
    ),
    ToolDefinition(
        name="investigate_strategy_failures",
        description="Run the accepted Phase 4 Strategy Failure Investigator for a symbol/range: population counts and FAILED-vs-NON_FAILED retrospective outcome and signal-time context comparison summaries. Descriptive association only, never causal.",
        parameters_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "start": {"type": "string", "description": _DATE_DESC},
                "end": {"type": "string", "description": _DATE_DESC},
                "interval": {"type": "string"},
            },
            "required": ["symbol", "start", "end"],
        },
        handler=investigate_strategy_failures,
    ),
    ToolDefinition(
        name="search_research_knowledge",
        description="Search the accepted Phase 5A authoritative TradeLens methodology knowledge base for passages relevant to a question.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "description": "Default 5."},
            },
            "required": ["query"],
        },
        handler=search_research_knowledge,
    ),
)
