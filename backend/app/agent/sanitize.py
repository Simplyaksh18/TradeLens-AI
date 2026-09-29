"""Phase 5C: strips model-generated citation-marker artifacts from final
display text.

Phase 5B manual verification showed Groq can emit citation-looking
markers such as `【7】` or `【1+L1-L3】` even though TradeLens's own
application-controlled source provenance (`ResearchAgentResult.
knowledge_sources`/`tool_trace`) is the only authoritative attribution.
Left in place, these look like real citations to a user but point at
nothing TradeLens controls. This module removes ONLY that specific
bracket-marker pattern -- it must never alter legitimate financial
content (numbers, percentages, currency, dates, condition names all pass
through untouched)."""

from __future__ import annotations

import re

# U+3010/U+3011 ("light brackets") wrapping short marker-like content --
# the exact shape Groq emitted in Phase 5B manual verification. Bounded
# and non-greedy so it can never accidentally swallow an entire answer.
_CITATION_MARKER_RE = re.compile(r"【[^【】]{0,40}】")


def strip_citation_markers(text: str) -> str:
    """Remove citation-marker artifacts, then collapse any resulting
    doubled whitespace left behind at the removal point. Never touches
    text outside the matched marker brackets."""
    without_markers = _CITATION_MARKER_RE.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", without_markers)
