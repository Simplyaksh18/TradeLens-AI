"""Phase 5B: deterministic evidence-sufficiency heuristic.

Phase 5A's retriever always returns up to `top_k` results, even for a
topic TradeLens's knowledge does not address at all -- a nonzero
similarity score does not by itself mean the retrieved evidence actually
answers the question (documented Phase 5A lexical-retrieval limitation).
This module implements the smallest deterministic check that catches an
obviously unsupported question before an LLM call is made.

MECHANISM (a coverage heuristic, NOT a probability/confidence score):
for each of the question's stemmed content tokens -- using the exact
same tokenizer/stemmer/stopword list Phase 5A's embedding provider uses
(`app.knowledge.embedding.tokenize`, reused, not duplicated) -- look up
how many corpus chunks contain that exact token. A token found in only a
few chunks is topically distinctive; one found in most chunks
(interrogative words, "TradeLens", "approved", generic "strategy" talk)
is not. Evidence is judged sufficient only if the question contains at
least one sufficiently distinctive token that TradeLens's own knowledge
base actually contains.

CALIBRATION (documented, not hidden): `MIN_DISTINCTIVE_IDF` was chosen
against the fixed CLAUDE.md Phase 5B evaluation set -- 5 canonical
answerable questions plus 2 deliberately unsupported/off-topic
questions ("Elliott Wave strategy", "weather in Mumbai"). The 5
answerable questions all score >= 3.37; the 2 unsupported questions
score <= 2.27. `3.0` sits in that gap with margin on both sides. This is
a fixed, testable, documented cutoff -- it has no statistical or
probabilistic meaning beyond "how rare is this term in the corpus."
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from app.knowledge.chunker import chunk_document
from app.knowledge.embedding import tokenize
from app.knowledge.loader import DEFAULT_CORPUS_DIR, load_corpus

# See module docstring "CALIBRATION" above.
MIN_DISTINCTIVE_IDF = 3.0

# Interrogative/meta-language filler that appears across nearly every
# question about TradeLens regardless of topic ("What is TradeLens
# approved X?", "Does X mean...", "Ignore the documents...") and so
# carries no topical signal for THIS heuristic specifically -- distinct
# from (and in addition to) app.knowledge.embedding's own stopword list,
# which is tuned for retrieval quality, not question-topic coverage.
_QUESTION_FILLER_STEMS = frozenset(
    {"what", "doe", "do", "did", "tell", "ignor", "document", "me", "allow", "tradelen", "approv"}
)


class EvidenceSufficiencyAssessor:
    """Builds a corpus-wide token document-frequency table once (cheap --
    a few dozen chunks) and reuses it for every `is_sufficient` call."""

    def __init__(self, corpus_dir: Path = DEFAULT_CORPUS_DIR):
        documents = load_corpus(corpus_dir)
        chunk_token_sets = [
            set(tokenize(chunk.content)) for document in documents for chunk in chunk_document(document)
        ]
        n_chunks = len(chunk_token_sets)

        document_frequency: Counter[str] = Counter()
        for token_set in chunk_token_sets:
            document_frequency.update(token_set)

        self._idf: dict[str, float] = {
            token: math.log((1 + n_chunks) / (1 + df)) + 1.0 for token, df in document_frequency.items()
        }

    def is_sufficient(self, question: str) -> bool:
        tokens = [tok for tok in tokenize(question) if tok not in _QUESTION_FILLER_STEMS]
        scores = [self._idf[tok] for tok in tokens if tok in self._idf]
        max_idf = max(scores, default=0.0)
        return max_idf >= MIN_DISTINCTIVE_IDF
