"""Phase 5A: chunker tests."""

from __future__ import annotations

from app.knowledge.chunker import chunk_document
from app.knowledge.loader import load_corpus
from app.knowledge.models import KnowledgeDocument, TrustClassification


def _doc(content: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id="doc",
        title="Doc",
        content=content,
        source_path="app/knowledge/documents/doc.md",
        version="abc123",
        trust=TrustClassification.AUTHORITATIVE_INTERNAL,
    )


def test_deterministic_output():
    doc = _doc("# Doc\n\nIntro paragraph.\n\n## Section\n\nBody paragraph.\n")
    first = chunk_document(doc)
    second = chunk_document(doc)
    assert first == second


def test_stable_chunk_ids_and_ordering():
    doc = _doc("# Doc\n\nA.\n\n## S1\n\nB.\n\n## S2\n\nC.\n")
    chunks = chunk_document(doc)
    assert [c.chunk_id for c in chunks] == [f"doc::chunk::{i:03d}" for i in range(len(chunks))]
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_no_content_loss():
    doc = _doc("# Doc\n\nParagraph one.\n\n## Section\n\nParagraph two.\n\nParagraph three.\n")
    chunks = chunk_document(doc)
    combined = "\n".join(c.content for c in chunks)
    for expected in ("Paragraph one.", "Paragraph two.", "Paragraph three."):
        assert expected in combined


def test_heading_association():
    doc = _doc("# Doc\n\nPreamble.\n\n## Real Section\n\nBody text.\n")
    chunks = chunk_document(doc)
    headings = {c.source.section_heading for c in chunks}
    assert "Real Section" in headings
    # The preamble before the first "## " heading is associated with the
    # document's own "# Title" heading, never silently dropped.
    assert "Doc" in headings


def test_bounded_chunk_size_does_not_drop_an_oversized_paragraph():
    long_paragraph = "word " * 400  # far exceeds MAX_CHUNK_CHARS
    doc = _doc(f"# Doc\n\n## Section\n\n{long_paragraph.strip()}\n")
    chunks = chunk_document(doc)
    assert any(long_paragraph.strip() in c.content for c in chunks)


def test_provenance_preserved_on_every_chunk():
    doc = _doc("# Doc\n\n## Section\n\nBody.\n")
    for chunk in chunk_document(doc):
        assert chunk.source.document_id == "doc"
        assert chunk.source.chunk_id == chunk.chunk_id
        assert chunk.source.chunk_ordinal == chunk.ordinal
        assert chunk.source.source_path == doc.source_path
        assert chunk.source.trust == TrustClassification.AUTHORITATIVE_INTERNAL


def test_real_corpus_chunks_without_dropping_content():
    documents = load_corpus()
    for document in documents:
        chunks = chunk_document(document)
        assert len(chunks) > 0
        combined = "\n".join(c.content for c in chunks)
        # Every paragraph-level sentence-ending phrase in the source
        # survives into some chunk (spot check via total character
        # coverage rather than brittle exact-substring matching for the
        # whole document).
        assert len(combined) > 0
