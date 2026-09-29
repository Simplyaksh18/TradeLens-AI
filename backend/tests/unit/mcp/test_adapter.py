"""Phase 5D: MCP adapter tests. No network, no Groq, no real MCP
transport -- direct calls to `app.mcp.adapter`, mirroring how
`app.mcp.server`'s handlers use it. Verifies the adapter is a pure
pass-through onto the accepted Phase 5C `TOOL_REGISTRY`: same names,
same descriptions, same schemas, same handler, same normalized output,
with zero financial recalculation or reinterpretation."""

from __future__ import annotations

from app.agent.registry import TOOL_REGISTRY
from app.agent.tools import audit_strategy_decision as direct_audit_strategy_decision
from app.mcp.adapter import call_mcp_tool, list_mcp_tools
from tests.unit.agent.conftest import FIXTURE_END, FIXTURE_KNOWN_BUY_DATE, FIXTURE_START

EXPECTED_TOOL_NAMES = {
    "search_instruments",
    "get_strategy_evaluation",
    "get_signal_outcomes",
    "run_backtest",
    "get_performance_analytics",
    "audit_strategy_decision",
    "investigate_strategy_failures",
    "search_research_knowledge",
}


# ---------------------------------------------------------------------------
# 1-4: MCP tool listing mirrors the accepted registry exactly
# ---------------------------------------------------------------------------


def test_mcp_exposes_exactly_the_accepted_registered_tools():
    names = {t.name for t in list_mcp_tools()}
    assert names == EXPECTED_TOOL_NAMES
    assert names == set(TOOL_REGISTRY.keys())


def test_mcp_tool_descriptions_derive_from_accepted_tool_definitions():
    by_name = {t.name: t for t in list_mcp_tools()}
    for name, tool_def in TOOL_REGISTRY.items():
        assert by_name[name].description == tool_def.description


def test_mcp_tool_input_schemas_match_accepted_tool_definitions_exactly():
    by_name = {t.name: t for t in list_mcp_tools()}
    for name, tool_def in TOOL_REGISTRY.items():
        assert by_name[name].inputSchema == tool_def.parameters_schema


def test_mcp_input_schema_represents_required_and_optional_fields():
    by_name = {t.name: t for t in list_mcp_tools()}
    schema = by_name["get_strategy_evaluation"].inputSchema
    assert schema["required"] == ["symbol", "start", "end"]
    assert "target_date" in schema["properties"]  # optional, not in required


# ---------------------------------------------------------------------------
# 5-6: invoking an MCP tool reaches the SAME registered handler, unaltered
# ---------------------------------------------------------------------------


def test_calling_an_mcp_tool_reaches_the_same_registered_handler_and_result(deps):
    mcp_result = call_mcp_tool(
        "audit_strategy_decision",
        {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END},
        deps,
    )
    direct_result = direct_audit_strategy_decision(
        {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END}, deps
    )
    assert mcp_result.isError is False
    assert mcp_result.structuredContent == direct_result.data


def test_normalized_structured_result_preserved_for_get_signal_outcomes(deps):
    result = call_mcp_tool("get_signal_outcomes", {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.isError is False
    assert result.structuredContent["count"] == len(result.structuredContent["outcomes"])


# ---------------------------------------------------------------------------
# 7: invalid arguments fail safely (no crash, no traceback)
# ---------------------------------------------------------------------------


def test_invalid_arguments_fail_safely(deps):
    result = call_mcp_tool("search_instruments", {"query": "   "}, deps)
    assert result.isError is True
    assert "Traceback" not in result.structuredContent["error_message"]
    assert result.structuredContent["error_code"] == "INVALID_ARGUMENT"


def test_unknown_symbol_fails_safely_not_as_crash(deps):
    result = call_mcp_tool("get_strategy_evaluation", {"symbol": "TOTALLY_FAKE_SYMBOL", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.isError is True
    assert "Traceback" not in result.structuredContent["error_message"]


# ---------------------------------------------------------------------------
# 8-9: unknown/unregistered/dangerous tool names cannot execute
# ---------------------------------------------------------------------------


def test_unknown_tool_name_cannot_execute(deps):
    result = call_mcp_tool("read_env", {}, deps)
    assert result.isError is True
    assert result.structuredContent["error_code"] == "UNKNOWN_TOOL"


def test_no_secret_env_filesystem_or_shell_tool_is_exposed():
    names = {t.name for t in list_mcp_tools()}
    forbidden = {"read_env", "execute_python", "run_shell", "delete_database", "arbitrary_http_request", "read_file"}
    assert names.isdisjoint(forbidden)


def test_arbitrary_dangerous_tool_names_all_rejected(deps):
    for dangerous_name in ("read_env", "execute_python", "delete_database", "run_shell", "arbitrary_http_request"):
        result = call_mcp_tool(dangerous_name, {}, deps)
        assert result.isError is True
        assert result.structuredContent["error_code"] == "UNKNOWN_TOOL"


# ---------------------------------------------------------------------------
# 10: audit_strategy_decision preserves the accepted 4-part structure
# ---------------------------------------------------------------------------


def test_audit_structure_preserved_through_mcp(deps):
    result = call_mcp_tool(
        "audit_strategy_decision",
        {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END},
        deps,
    )
    data = result.structuredContent
    assert result.isError is False
    assert "decision" in data
    assert "decision_evidence" in data
    assert "point_in_time_context" in data
    assert "retrospective_hindsight" in data
    # never flattened back: context/hindsight fields stay nested, not top-level
    assert "regime" not in data
    assert "five_bar_hit_rate" not in data


# ---------------------------------------------------------------------------
# 11: search_research_knowledge preserves full provenance
# ---------------------------------------------------------------------------


def test_search_research_knowledge_preserves_provenance_through_mcp(deps):
    result = call_mcp_tool("search_research_knowledge", {"query": "What conditions trigger Trend + Momentum v1?"}, deps)
    assert result.isError is False
    first = result.structuredContent["results"][0]
    for key in ("chunk_id", "document_id", "document_title", "source_path", "section_heading", "trust", "score", "content"):
        assert key in first


# ---------------------------------------------------------------------------
# 12: deterministic financial output is not recalculated/modified by MCP
# ---------------------------------------------------------------------------


def test_mcp_does_not_recalculate_or_modify_financial_output(deps):
    args = {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}
    direct = TOOL_REGISTRY["get_performance_analytics"].handler(args, deps)
    via_mcp = call_mcp_tool("get_performance_analytics", args, deps)
    assert via_mcp.structuredContent == direct.data  # byte-identical, no rounding/renaming/derivation


# ---------------------------------------------------------------------------
# 13: tool application errors map safely (non-trading audit date)
# ---------------------------------------------------------------------------


def test_audit_date_not_a_trading_bar_maps_to_safe_error(deps):
    result = call_mcp_tool(
        "audit_strategy_decision", {"symbol": "RELIANCE", "audit_date": "1999-01-01", "start": FIXTURE_START, "end": FIXTURE_END}, deps
    )
    assert result.isError is True
    assert result.structuredContent["error_code"] == "AUDIT_DATE_NOT_A_TRADING_BAR"
