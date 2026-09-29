"""Phase 5A: deterministic domain models for the research knowledge/
retrieval foundation. No LLM, no generated prose -- these models carry
evidence and provenance only (see CLAUDE.md Phase 5A)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrustClassification(str, Enum):
    """Source trust class, preserved so a later phase (5B) can distinguish
    controlled TradeLens knowledge from any future untrusted source. Phase
    5A's built-in corpus is always AUTHORITATIVE_INTERNAL; no other class
    is produced by this phase."""

    AUTHORITATIVE_INTERNAL = "AUTHORITATIVE_INTERNAL"


@dataclass(frozen=True)
class KnowledgeDocument:
    """One loaded, whole Markdown document from the controlled corpus."""

    document_id: str
    title: str
    content: str
    source_path: str
    version: str
    trust: TrustClassification


@dataclass(frozen=True)
class SourceReference:
    """Provenance for one retrievable chunk -- enough for a future caller
    to cite exactly which TradeLens knowledge supported a statement."""

    document_id: str
    document_title: str
    source_path: str
    chunk_id: str
    chunk_ordinal: int
    section_heading: str | None
    trust: TrustClassification


@dataclass(frozen=True)
class KnowledgeChunk:
    """One deterministically-produced, ordered slice of a document."""

    chunk_id: str
    document_id: str
    content: str
    ordinal: int
    source: SourceReference


@dataclass(frozen=True)
class RetrievalResult:
    """One ranked retrieval hit: evidence, never synthesized prose."""

    chunk: KnowledgeChunk
    score: float
