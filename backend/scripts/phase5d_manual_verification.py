"""Phase 5D manual acceptance helper (not a test -- run manually).

Launches the REAL TradeLens MCP server as a subprocess (`python -m
app.mcp.server`, the actual STDIO entry point) and drives it with the
official MCP Python SDK's `stdio_client`/`ClientSession` -- a genuine
external-process protocol round trip, not an in-process shortcut. Uses
the real accepted market-data/instrument-master/knowledge-retriever
dependencies (live yfinance path for the deterministic tool call, same as
native dev) -- Groq/GROQ_API_KEY is never touched anywhere in this
script, since MCP tool execution has no LLM in it (Phase 5C's Groq agent
and this MCP server are sibling consumers of the same registry).

Run with:

    cd backend
    PYTHONPATH=. python scripts/phase5d_manual_verification.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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

# Real, previously-accepted RELIANCE manual-verification fixture dates
# (same as Phase 3D/3E/5C -- CLAUDE.md).
KNOWN_AUDIT_DATE = "2024-06-13"
KNOWN_START = "2023-01-01"
KNOWN_END = "2024-06-30"


async def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    child_env = dict(os.environ)
    child_env["PYTHONPATH"] = str(backend_dir)
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.server"],
        cwd=str(backend_dir),
        env=child_env,
    )

    print("PHASE 5D MCP SERVER VERIFICATION (STDIO subprocess, official MCP client)")
    print("  GROQ_API_KEY is NOT required for this script -- MCP tool execution has no LLM in it.")
    print()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # A. list tools
            listed = await session.list_tools()
            names = {t.name for t in listed.tools}
            print(f"[A] list_tools -> {sorted(names)}")
            print(f"    [{'PASS' if names == EXPECTED_TOOL_NAMES else 'FAIL'}] exactly the accepted TradeLens MCP tool names")
            print()

            # B. knowledge tool
            b = await session.call_tool("search_research_knowledge", {"query": "Trend + Momentum v1 BUY conditions"})
            b_data = b.structuredContent or {}
            b_results = b_data.get("results", [])
            b_ok = (
                not b.isError
                and bool(b_results)
                and all(k in b_results[0] for k in ("chunk_id", "document_id", "document_title", "section_heading", "trust", "score"))
            )
            print(f"[B] search_research_knowledge -> {len(b_results)} result(s)")
            if b_results:
                print(f"    top result: {b_results[0]['document_id']} :: {b_results[0]['section_heading']} (trust={b_results[0]['trust']})")
            print(f"    [{'PASS' if b_ok else 'FAIL'}] structured result contains authoritative provenance")
            print()

            # C. deterministic tool (live market data)
            c = await session.call_tool(
                "get_strategy_evaluation", {"symbol": "RELIANCE", "start": KNOWN_START, "end": KNOWN_END, "target_date": KNOWN_AUDIT_DATE}
            )
            c_data = c.structuredContent or {}
            c_ok = not c.isError and c_data.get("decision") in ("BUY", "NO_SIGNAL", "INSUFFICIENT_DATA")
            print(f"[C] get_strategy_evaluation(RELIANCE, {KNOWN_AUDIT_DATE}) -> decision={c_data.get('decision')}")
            print(f"    [{'PASS' if c_ok else 'FAIL'}] deterministic tool result returned through MCP")
            print()

            # D. audit structure
            d = await session.call_tool(
                "audit_strategy_decision", {"symbol": "RELIANCE", "audit_date": KNOWN_AUDIT_DATE, "start": KNOWN_START, "end": KNOWN_END}
            )
            d_data = d.structuredContent or {}
            d_ok = not d.isError and all(
                k in d_data for k in ("decision", "decision_evidence", "point_in_time_context", "retrospective_hindsight")
            )
            print(f"[D] audit_strategy_decision -> decision={d_data.get('decision')}")
            print(f"    top-level keys: {sorted(d_data.keys())}")
            print(f"    [{'PASS' if d_ok else 'FAIL'}] decision/decision_evidence/point_in_time_context/retrospective_hindsight all present and separate")
            print()

            # E. rejection/safety
            e = await session.call_tool("read_env", {})
            e_ok = bool(e.isError)
            print(f"[E] read_env -> isError={e.isError}, content={e.structuredContent}")
            print(f"    [{'PASS' if e_ok else 'FAIL'}] unavailable tool cannot execute")
            print()

    print("ALL MANUAL PHASE 5D CHECKS PRINTED -- inspect PASS/FAIL lines above.")


if __name__ == "__main__":
    asyncio.run(main())
