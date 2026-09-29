"""Phase 5D: real MCP protocol integration test -- uses the official SDK's
in-memory client/server session (`mcp.shared.memory.
create_connected_server_and_client_session`) to exercise the ACTUAL MCP
protocol (JSON-RPC-shaped `list_tools`/`call_tool` requests through a real
`ClientSession` against a real `Server`), not a hand-faked adapter call.

This is a genuine protocol round-trip: client -> MCP session -> server ->
`app.mcp.adapter` -> the accepted Phase 5C `TOOL_REGISTRY` handler ->
deterministic fixture data (no yfinance network, no Groq) -> structured
result back through the protocol to the client. In-process memory streams
are used instead of a subprocess so the test runs fast and deterministically
under pytest without spawning `python -m app.mcp.server`."""

from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp.server import create_server
from tests.unit.agent.conftest import FIXTURE_END, FIXTURE_KNOWN_BUY_DATE, FIXTURE_START


@pytest.mark.anyio
async def test_real_mcp_client_list_tools_matches_accepted_registry(deps):
    server = create_server(deps)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
        assert names == {
            "search_instruments",
            "get_strategy_evaluation",
            "get_signal_outcomes",
            "run_backtest",
            "get_performance_analytics",
            "audit_strategy_decision",
            "investigate_strategy_failures",
            "search_research_knowledge",
        }


@pytest.mark.anyio
async def test_real_mcp_client_call_tool_reaches_registry_handler_and_returns_structured_result(deps):
    server = create_server(deps)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "audit_strategy_decision",
            {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END},
        )
        assert result.isError is not True
        data = result.structuredContent
        assert "decision" in data
        assert "decision_evidence" in data
        assert "point_in_time_context" in data
        assert "retrospective_hindsight" in data


@pytest.mark.anyio
async def test_real_mcp_client_unknown_tool_call_fails_safely(deps):
    server = create_server(deps)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("read_env", {})
        assert result.isError is True


@pytest.fixture
def anyio_backend():
    return "asyncio"
