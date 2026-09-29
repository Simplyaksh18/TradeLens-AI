"""Phase 5C: citation-marker sanitization tests."""

from __future__ import annotations

from app.agent.sanitize import strip_citation_markers


def test_removes_simple_numeric_marker():
    assert strip_citation_markers("The rule is X【7】.") == "The rule is X."


def test_removes_footnote_style_marker():
    text = "The rule is X【1+L1-L3】 and that is final."
    assert "【" not in strip_citation_markers(text)
    assert "final" in strip_citation_markers(text)


def test_removes_multiple_markers():
    text = "A【1】B【2】C"
    assert strip_citation_markers(text) == "ABC"


def test_does_not_alter_legitimate_financial_content():
    text = "close > SMA20 (strict), 40 <= RSI14 <= 70, return +6.84%, ₹1,465.25"
    assert strip_citation_markers(text) == text


def test_no_markers_present_is_a_no_op():
    text = "TradeLens never invents citations."
    assert strip_citation_markers(text) == text
