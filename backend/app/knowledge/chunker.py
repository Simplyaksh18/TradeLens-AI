"""Phase 5A: deterministic, structure-aware chunking of a
`KnowledgeDocument` into ordered `KnowledgeChunk`s. Splits on Markdown
heading/paragraph boundaries only -- no tokenizer dependency, no random
behavior, no semantic chunking. Never drops content: every non-blank
paragraph in the source document ends up in exactly one chunk."""

from __future__ import annotations

import re

from app.knowledge.models import KnowledgeChunk, KnowledgeDocument, SourceReference

# Generous relative to this corpus's short paragraphs (see CLAUDE.md
# Phase 5A) -- most "## " sections already fit in one chunk, avoiding
# unnecessary splitting of an accepted rule statement across chunks.
MAX_CHUNK_CHARS = 800

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def chunk_document(document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
    """Chunk `document.content` by Markdown heading sections, then by
    blank-line-separated paragraphs within each section, greedily packing
    paragraphs into a chunk up to `MAX_CHUNK_CHARS` (a single paragraph
    longer than that is still kept whole -- content is never truncated or
    dropped to satisfy the bound). Chunk ordering matches source order;
    `chunk_id` is `f"{document_id}::chunk::{ordinal:03d}"`, stable across
    runs for unchanged content."""
    sections = _split_into_sections(document.content)

    chunks: list[KnowledgeChunk] = []
    ordinal = 0
    for heading, body in sections:
        for chunk_text in _pack_paragraphs(body):
            chunk_id = f"{document.document_id}::chunk::{ordinal:03d}"
            source = SourceReference(
                document_id=document.document_id,
                document_title=document.title,
                source_path=document.source_path,
                chunk_id=chunk_id,
                chunk_ordinal=ordinal,
                section_heading=heading,
                trust=document.trust,
            )
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    content=chunk_text,
                    ordinal=ordinal,
                    source=source,
                )
            )
            ordinal += 1

    return tuple(chunks)


def _split_into_sections(content: str) -> list[tuple[str | None, str]]:
    """Split into (heading_text_or_None, section_body) pairs. The
    document's own `# Title` line becomes the heading of the first
    (preamble) section rather than being discarded."""
    lines = content.splitlines()
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    return [(heading, "\n".join(body_lines).strip()) for heading, body_lines in sections if "\n".join(body_lines).strip()]


def _pack_paragraphs(body: str) -> list[str]:
    """Greedily pack blank-line-separated paragraphs into chunks bounded
    by MAX_CHUNK_CHARS, never splitting a paragraph itself."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paragraphs:
        return []

    packed: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        added_len = len(paragraph) + (2 if current else 0)
        if current and current_len + added_len > MAX_CHUNK_CHARS:
            packed.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += added_len

    if current:
        packed.append("\n\n".join(current))

    return packed
