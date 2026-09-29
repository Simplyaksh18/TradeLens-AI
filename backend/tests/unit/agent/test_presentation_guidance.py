"""Text-presence regression tests for the Markdown-table presentation
guidance added to the system instruction (see CLAUDE.md Post-5F Research
Workspace acceptance follow-up, "Failure-Investigation Table
Presentation"). Mirrors the existing text-presence convention already
used by `tests/unit/agent/test_hardening.py`/`test_audit_semantics.py` --
we cannot assert what a live LLM will actually write, so these tests only
guard against a future edit silently dropping the rule."""

from __future__ import annotations

from app.agent.prompt import SYSTEM_INSTRUCTION


def test_system_instruction_directs_tables_for_comparative_metric_heavy_evidence():
    text = SYSTEM_INSTRUCTION.lower()
    assert "markdown table" in text
    assert "gfm" in text
    assert "failed vs. non_failed" in text or "failed vs. non-failed" in text


def test_system_instruction_forbids_computed_or_invented_table_cells():
    text = SYSTEM_INSTRUCTION.lower()
    assert "never compute a cell" in text
    assert "never invent a placeholder cell" in text


def test_system_instruction_still_allows_prose_for_non_comparative_answers():
    text = SYSTEM_INSTRUCTION.lower()
    assert "should stay prose" in text


def test_system_instruction_references_available_forward_bars_hindsight_reason():
    text = SYSTEM_INSTRUCTION.lower()
    assert "available_forward_bars" in text
