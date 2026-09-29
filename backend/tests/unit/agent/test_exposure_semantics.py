"""Phase 5E UI polish: exposure terminology regression test. Manual
verification found a live Groq answer describing `exposure` as "percentage
of capital allocated" -- incorrect for the accepted Phase 2C metric
(fraction of evaluated trading bars/time with an open position). The
exposure CALCULATION itself is unchanged; only the grounding/tool-
description text was clarified (see CLAUDE.md Phase 5E UI polish). No
live Groq call -- this only verifies the architecturally enforceable
text, matching the existing hardening-test convention."""

from __future__ import annotations

from app.agent.prompt import SYSTEM_INSTRUCTION
from app.agent.registry import get_tool


def test_performance_analytics_tool_description_defines_exposure_correctly():
    tool = get_tool("get_performance_analytics")
    lowered = tool.description.lower()
    assert "time-in-market" in lowered or "trading bars" in lowered
    assert "never a percentage of capital allocated" in lowered


def test_system_instruction_forbids_capital_allocation_exposure_language():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "time-in-market" in lowered
    assert "never describe \"exposure\" as a percentage of capital allocated" in lowered
