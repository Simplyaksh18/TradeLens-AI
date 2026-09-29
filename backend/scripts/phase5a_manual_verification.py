"""Phase 5A manual acceptance helper (not a test -- run manually).

Loads the REAL controlled knowledge corpus, indexes it through the real
deterministic pipeline (loader -> chunker -> LocalHashEmbeddingProvider ->
InMemoryVectorStore), and runs the five canonical retrieval-quality
queries, printing each ranked result's document, section, score, and a
short content preview for human inspection. No LLM. No network.

Run with:

    cd backend
    PYTHONPATH=. python scripts/phase5a_manual_verification.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore

CANONICAL_QUERIES = [
    "What conditions trigger Trend + Momentum v1?",
    "What does an unavailable 10-bar outcome mean?",
    "When is a backtest entry executed?",
    "Does a failed signal mean the strategy caused the loss?",
    "What information is allowed in a point-in-time audit?",
]


def main() -> None:
    retriever = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    chunk_count = retriever.index_corpus()

    print("PHASE 5A RETRIEVAL VERIFICATION")
    print(f"  indexed chunks: {chunk_count}")
    print()

    for query in CANONICAL_QUERIES:
        print(f"QUERY: {query}")
        results = retriever.retrieve(query, top_k=3)
        for rank, result in enumerate(results, start=1):
            preview = result.chunk.content.replace("\n", " ")[:100]
            print(
                f"  #{rank}  doc={result.chunk.document_id:<28} "
                f"section={result.chunk.source.section_heading!r:<30} "
                f"score={result.score:+.4f}"
            )
            print(f"       preview: {preview}...")
        print()

    print("ALL MANUAL PHASE 5A CHECKS PRINTED -- inspect above for relevance.")


if __name__ == "__main__":
    main()
