"""Phase 5A: deterministic loader for the controlled Markdown knowledge
corpus (app/knowledge/documents/). No network, no dynamic web crawling,
no arbitrary user filesystem ingestion -- only the fixed, version-
controlled corpus directory shipped with the application."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.exceptions import KnowledgeCorpusInvalidError
from app.knowledge.models import KnowledgeDocument, TrustClassification

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parent / "documents"


def load_corpus(corpus_dir: Path = DEFAULT_CORPUS_DIR) -> tuple[KnowledgeDocument, ...]:
    """Load every `*.md` file in `corpus_dir` into `KnowledgeDocument`s.

    Deterministic ordering: files are sorted by filename (stable, not
    filesystem/OS directory-listing order). `document_id` is the filename
    stem (e.g. `strategy_trend_momentum_v1`), so it is stable across runs.
    Every document's leading non-blank line must be a level-1 Markdown
    heading (`# Title`) -- that becomes `title`; the full raw content
    (including the heading) is preserved as `content`. `version` is a
    short deterministic content hash, so a corpus edit is detectable
    without hand-maintained version numbers.

    Raises KnowledgeCorpusInvalidError for an empty document, a document
    missing its leading `# Title` heading, or a duplicate `document_id`.
    """
    paths = sorted(corpus_dir.glob("*.md"), key=lambda p: p.name)
    documents: list[KnowledgeDocument] = []
    seen_ids: set[str] = set()

    for path in paths:
        raw = path.read_text(encoding="utf-8")
        content = raw.strip("\n")
        if not content.strip():
            raise KnowledgeCorpusInvalidError(f"Empty knowledge document: {path.name!r}")

        first_line = content.splitlines()[0].strip()
        if not first_line.startswith("# "):
            raise KnowledgeCorpusInvalidError(
                f"Knowledge document {path.name!r} must start with a level-1 '# Title' heading"
            )
        title = first_line[2:].strip()
        if not title:
            raise KnowledgeCorpusInvalidError(f"Knowledge document {path.name!r} has an empty title heading")

        document_id = path.stem
        if document_id in seen_ids:
            raise KnowledgeCorpusInvalidError(f"Duplicate knowledge document_id: {document_id!r}")
        seen_ids.add(document_id)

        version = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]

        documents.append(
            KnowledgeDocument(
                document_id=document_id,
                title=title,
                content=content,
                source_path=f"app/knowledge/documents/{path.name}"
                if corpus_dir == DEFAULT_CORPUS_DIR
                else str(path.relative_to(corpus_dir)).replace("\\", "/"),
                version=version,
                trust=TrustClassification.AUTHORITATIVE_INTERNAL,
            )
        )

    return tuple(documents)
