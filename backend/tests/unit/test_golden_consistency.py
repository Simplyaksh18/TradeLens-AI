"""Phase 5F Part E: golden end-to-end consistency. Proves the SAME
deterministic truth survives across every interface TradeLens exposes it
through -- domain engine, REST API, Phase 5C agent tool, and Phase 5D MCP
adapter -- for one shared, fixed fixture (the same `FIXTURE_SERIES`
already used by every Phase 5C/5D test, so this file introduces no new
fixture shape). No network, no live yfinance, no Groq -- every layer is
exercised directly/deterministically.

Six representative cases (CLAUDE.md Phase 5F Part E, items 1-6):
  1. strategy BUY decision + evidence
  2. signal outcome
  3. backtest/performance
  4. audit structure
  5. failure investigation
  6. knowledge provenance
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agent.registry import TOOL_REGISTRY
from app.api.dependencies import get_agent_dependencies, get_instrument_master, get_market_data_service
from app.api.research import build_strategy_research
from app.api.dependencies import HistoryQueryParams
from app.audit.engine import build_strategy_audit
from app.backtesting.engine import run_backtest as run_backtest_engine
from app.backtesting.models import BacktestConfig
from app.analytics.engine import compute_performance_analytics
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.composer import build_strategy_failure_investigation
from app.investigation.context import build_failure_context_dataset
from app.investigation.engine import build_signal_investigation_dataset
from app.mcp.adapter import call_mcp_tool
from app.main import app
from app.outcomes.engine import compute_signal_outcomes
from app.agent.dependencies import AgentDependencies
from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore
from tests.unit.agent.conftest import (
    FIXTURE_END,
    FIXTURE_KNOWN_BUY_DATE,
    FIXTURE_START,
    FIXTURE_SERIES,
    FakeInstrumentMaster,
    FakeMarketDataService,
)


@pytest.fixture(scope="module")
def _knowledge_retriever() -> ResearchKnowledgeRetriever:
    r = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    r.index_corpus()
    return r


@pytest.fixture
def agent_deps(_knowledge_retriever) -> AgentDependencies:
    return AgentDependencies(
        market_data_service=FakeMarketDataService(FIXTURE_SERIES),
        instrument_master=FakeInstrumentMaster(),
        knowledge_retriever=_knowledge_retriever,
    )


@pytest.fixture
def rest_client(agent_deps):
    app.dependency_overrides[get_market_data_service] = lambda: agent_deps.market_data_service
    app.dependency_overrides[get_instrument_master] = lambda: agent_deps.instrument_master
    app.dependency_overrides[get_agent_dependencies] = lambda: agent_deps
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


_PARAMS = HistoryQueryParams(start=FIXTURE_SERIES.bars[0].date, end=FIXTURE_SERIES.bars[-1].date, interval="1d")


def _domain_pipeline(deps):
    market_series, indicator_series, evaluation_series = build_strategy_research("RELIANCE", _PARAMS, deps.market_data_service)
    outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    return market_series, indicator_series, evaluation_series, outcome_series


# ---------------------------------------------------------------------------
# 1. Strategy BUY decision + evidence
# ---------------------------------------------------------------------------


def test_golden_strategy_decision_consistent_across_rest_and_agent(agent_deps, rest_client):
    _, _, evaluation_series, _ = _domain_pipeline(agent_deps)
    domain_row = next(e for e in evaluation_series.evaluations if e.date.isoformat() == FIXTURE_KNOWN_BUY_DATE)

    rest_response = rest_client.get(
        f"/api/v1/strategies/trend-momentum-v1/RELIANCE",
        params={"start": FIXTURE_START, "end": FIXTURE_END, "interval": "1d"},
    )
    assert rest_response.status_code == 200
    rest_row = next(e for e in rest_response.json()["evaluations"] if e["date"] == FIXTURE_KNOWN_BUY_DATE)
    assert rest_row["decision"] == domain_row.decision.value

    agent_result = TOOL_REGISTRY["get_strategy_evaluation"].handler(
        {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END, "target_date": FIXTURE_KNOWN_BUY_DATE}, agent_deps
    )
    assert agent_result.data["decision"] == domain_row.decision.value
    for domain_cond, agent_cond in zip(domain_row.conditions, agent_result.data["conditions"]):
        assert domain_cond.condition_id == agent_cond["condition_id"]
        assert domain_cond.passed == agent_cond["passed"]


# ---------------------------------------------------------------------------
# 2. Signal outcome
# ---------------------------------------------------------------------------


def test_golden_signal_outcome_consistent_across_rest_and_agent(agent_deps, rest_client):
    _, _, _, outcome_series = _domain_pipeline(agent_deps)
    domain_outcome = outcome_series.outcomes[0]

    rest_response = rest_client.get(
        "/api/v1/outcomes/trend-momentum-v1/RELIANCE", params={"start": FIXTURE_START, "end": FIXTURE_END, "interval": "1d"}
    )
    rest_outcome = rest_response.json()["outcomes"][0]
    assert rest_outcome["reference_close"] == domain_outcome.reference_close
    assert rest_outcome["forward_return_10d"] == domain_outcome.forward_return_10d

    agent_result = TOOL_REGISTRY["get_signal_outcomes"].handler({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, agent_deps)
    agent_outcome = agent_result.data["outcomes"][0]
    assert agent_outcome["reference_close"] == domain_outcome.reference_close
    assert agent_outcome["mae_10d"] == domain_outcome.mae_10d


# ---------------------------------------------------------------------------
# 3. Backtest / performance analytics
# ---------------------------------------------------------------------------


def test_golden_performance_analytics_consistent_across_rest_agent_and_mcp(agent_deps, rest_client):
    market_series, _, evaluation_series, _ = _domain_pipeline(agent_deps)
    backtest_result = run_backtest_engine(market_series, evaluation_series, BacktestConfig(initial_capital=100_000.0))
    domain_analytics = compute_performance_analytics(backtest_result)

    rest_response = rest_client.get(
        "/api/v1/analytics/trend-momentum-v1/RELIANCE", params={"start": FIXTURE_START, "end": FIXTURE_END, "interval": "1d"}
    )
    rest_data = rest_response.json()
    assert rest_data["total_return"] == domain_analytics.total_return
    assert rest_data["maximum_drawdown"] == domain_analytics.maximum_drawdown

    args = {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}
    agent_result = TOOL_REGISTRY["get_performance_analytics"].handler(args, agent_deps)
    assert agent_result.data["total_return"] == domain_analytics.total_return
    assert agent_result.data["win_rate"] == domain_analytics.win_rate

    mcp_result = call_mcp_tool("get_performance_analytics", args, agent_deps)
    assert mcp_result.structuredContent == agent_result.data  # MCP is a pure pass-through onto the same handler


# ---------------------------------------------------------------------------
# 4. Audit structure
# ---------------------------------------------------------------------------


def test_golden_audit_structure_consistent_across_rest_agent_and_mcp(agent_deps, rest_client):
    market_series, indicator_series, evaluation_series, outcome_series = _domain_pipeline(agent_deps)
    from datetime import date as Date

    audit_date = Date.fromisoformat(FIXTURE_KNOWN_BUY_DATE)
    domain_audit = build_strategy_audit(
        market_series, evaluation_series, outcome_series, indicator_series, audit_date, evidence_start_date=FIXTURE_SERIES.bars[0].date
    )

    rest_response = rest_client.get(
        "/api/v1/audits/trend-momentum-v1/RELIANCE",
        params={"start": FIXTURE_START, "end": FIXTURE_END, "interval": "1d", "audit_date": FIXTURE_KNOWN_BUY_DATE},
    )
    rest_data = rest_response.json()
    assert rest_data["evaluation"]["decision"] == domain_audit.evaluation.decision.value
    assert rest_data["risk_market_context"]["regime"] == domain_audit.risk_market_context.regime.value

    args = {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END}
    agent_result = TOOL_REGISTRY["audit_strategy_decision"].handler(args, agent_deps)
    assert agent_result.data["decision"] == domain_audit.evaluation.decision.value
    assert agent_result.data["point_in_time_context"]["regime"] == domain_audit.risk_market_context.regime.value

    mcp_result = call_mcp_tool("audit_strategy_decision", args, agent_deps)
    assert mcp_result.structuredContent == agent_result.data
    # the audit 4-part structure is never flattened at any layer
    for key in ("decision", "decision_evidence", "point_in_time_context", "retrospective_hindsight"):
        assert key in mcp_result.structuredContent


# ---------------------------------------------------------------------------
# 5. Failure investigation
# ---------------------------------------------------------------------------


def test_golden_failure_investigation_consistent_across_rest_agent_and_mcp(agent_deps, rest_client):
    market_series, indicator_series, evaluation_series, outcome_series = _domain_pipeline(agent_deps)
    dataset = build_signal_investigation_dataset(outcome_series)
    comparison = build_failure_population_comparison(dataset)
    context = build_failure_context_dataset(dataset, market_series, indicator_series)
    domain_investigation = build_strategy_failure_investigation(dataset, comparison, context)

    rest_response = rest_client.get(
        "/api/v1/investigations/trend-momentum-v1/RELIANCE", params={"start": FIXTURE_START, "end": FIXTURE_END, "interval": "1d"}
    )
    rest_data = rest_response.json()
    assert rest_data["failed_count"] == domain_investigation.failed_count
    assert rest_data["non_failed_count"] == domain_investigation.non_failed_count

    args = {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}
    agent_result = TOOL_REGISTRY["investigate_strategy_failures"].handler(args, agent_deps)
    assert agent_result.data["total_signal_count"] == domain_investigation.total_signal_count
    assert agent_result.data["failed_average_return"] == domain_investigation.outcome_comparison.failed.average_forward_return_10d

    mcp_result = call_mcp_tool("investigate_strategy_failures", args, agent_deps)
    assert mcp_result.structuredContent == agent_result.data


# ---------------------------------------------------------------------------
# 6. Knowledge provenance
# ---------------------------------------------------------------------------


def test_golden_knowledge_provenance_consistent_across_agent_and_mcp(agent_deps):
    query = "What are the exact BUY conditions for Trend + Momentum v1?"
    direct_results = agent_deps.knowledge_retriever.retrieve(query, top_k=5)

    args = {"query": query}
    agent_result = TOOL_REGISTRY["search_research_knowledge"].handler(args, agent_deps)
    assert agent_result.data["results"][0]["chunk_id"] == direct_results[0].chunk.source.chunk_id
    assert agent_result.data["results"][0]["document_id"] == direct_results[0].chunk.source.document_id

    mcp_result = call_mcp_tool("search_research_knowledge", args, agent_deps)
    assert mcp_result.structuredContent == agent_result.data
