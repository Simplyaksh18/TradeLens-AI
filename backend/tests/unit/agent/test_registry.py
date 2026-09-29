"""Phase 5C: tool allowlist tests."""

from __future__ import annotations

from app.agent.registry import TOOL_REGISTRY, get_tool

EXPECTED_TOOLS = {
    "search_instruments",
    "get_strategy_evaluation",
    "get_signal_outcomes",
    "run_backtest",
    "get_performance_analytics",
    "audit_strategy_decision",
    "investigate_strategy_failures",
    "search_research_knowledge",
}


def test_registry_contains_exactly_the_approved_tools():
    assert set(TOOL_REGISTRY.keys()) == EXPECTED_TOOLS


def test_get_tool_returns_none_for_unregistered_names():
    for dangerous_name in ("delete_database", "execute_python", "run_shell", "read_env", "get_api_key", "arbitrary_http_request"):
        assert get_tool(dangerous_name) is None


def test_get_tool_returns_definition_for_registered_name():
    tool = get_tool("search_research_knowledge")
    assert tool is not None
    assert tool.name == "search_research_knowledge"
    assert tool.parameters_schema["type"] == "object"
