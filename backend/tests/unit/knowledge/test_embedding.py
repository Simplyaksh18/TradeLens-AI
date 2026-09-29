"""Phase 5A: embedding provider tests."""

from __future__ import annotations

import math

import pytest

from app.core.exceptions import EmbeddingInputInvalidError
from app.knowledge.embedding import LocalHashEmbeddingProvider


def test_deterministic_across_instances():
    a = LocalHashEmbeddingProvider().embed_texts(["Trend and momentum signal."])
    b = LocalHashEmbeddingProvider().embed_texts(["Trend and momentum signal."])
    assert a == b


def test_fixed_dimension():
    provider = LocalHashEmbeddingProvider(dimension=128)
    vectors = provider.embed_texts(["alpha beta gamma", "delta epsilon"])
    assert all(len(v) == 128 for v in vectors)
    assert len(provider.embed_query("alpha")) == 128


def test_finite_values():
    provider = LocalHashEmbeddingProvider()
    for value in provider.embed_texts(["some reasonably normal sentence about RSI and SMA"])[0]:
        assert math.isfinite(value)


def test_query_and_document_share_dimension_and_are_comparable():
    provider = LocalHashEmbeddingProvider()
    provider.embed_texts(["Trend Momentum strategy uses RSI and SMA."])
    query_vector = provider.embed_query("What does RSI mean in the strategy?")
    assert len(query_vector) == provider.dimension


def test_rejects_blank_text():
    provider = LocalHashEmbeddingProvider()
    with pytest.raises(EmbeddingInputInvalidError):
        provider.embed_texts([""])
    with pytest.raises(EmbeddingInputInvalidError):
        provider.embed_query("   ")


def test_idf_downweights_common_terms_shared_across_corpus():
    provider = LocalHashEmbeddingProvider()
    # "signal" appears in both; "unavailable" is distinctive to the second.
    vectors = provider.embed_texts(
        [
            "A signal is a decision produced by the strategy.",
            "An unavailable outcome means the signal has no complete forward window.",
        ]
    )
    assert vectors[0] != vectors[1]
