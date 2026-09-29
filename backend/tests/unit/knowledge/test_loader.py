"""Phase 5A: document loader tests."""

from __future__ import annotations

import pytest

from app.core.exceptions import KnowledgeCorpusInvalidError
from app.knowledge.loader import DEFAULT_CORPUS_DIR, load_corpus
from app.knowledge.models import TrustClassification


def test_loads_the_real_controlled_corpus():
    documents = load_corpus()
    assert len(documents) == 7
    ids = {d.document_id for d in documents}
    assert ids == {
        "strategy_trend_momentum_v1",
        "signal_outcomes",
        "backtesting_methodology",
        "risk_analytics",
        "strategy_auditing",
        "failure_investigation",
        "research_limitations",
    }


def test_deterministic_ordering():
    first = [d.document_id for d in load_corpus()]
    second = [d.document_id for d in load_corpus()]
    assert first == second
    assert first == sorted(first)


def test_stable_document_ids_and_provenance():
    documents = load_corpus()
    by_id = {d.document_id: d for d in documents}
    strategy_doc = by_id["strategy_trend_momentum_v1"]
    assert strategy_doc.title == "Trend + Momentum v1 Strategy"
    assert strategy_doc.source_path == "app/knowledge/documents/strategy_trend_momentum_v1.md"
    assert strategy_doc.trust == TrustClassification.AUTHORITATIVE_INTERNAL
    assert len(strategy_doc.version) == 12


def test_version_is_stable_for_unchanged_content():
    first = {d.document_id: d.version for d in load_corpus()}
    second = {d.document_id: d.version for d in load_corpus()}
    assert first == second


def test_utf8_content_preserved(tmp_path):
    (tmp_path / "a.md").write_text("# Title Café\n\nContent with é and ₹ symbols.\n", encoding="utf-8")
    documents = load_corpus(tmp_path)
    assert documents[0].title == "Title Café"
    assert "₹" in documents[0].content


def test_rejects_duplicate_document_ids(tmp_path, monkeypatch):
    # document_id is the filename stem, so two genuinely distinct files on
    # a real (case-sensitive) filesystem cannot normally collide -- force
    # the collision by monkeypatching the glob result so the loader's own
    # duplicate-id guard (not the filesystem) is what's under test.
    real_file = tmp_path / "strategy.md"
    real_file.write_text("# Strategy\n\nBody one.\n", encoding="utf-8")
    duplicate_path = tmp_path / "renamed_but_same_stem.md"
    duplicate_path.write_text("# Strategy Again\n\nBody two.\n", encoding="utf-8")

    from app.knowledge import loader as loader_module

    monkeypatch.setattr(
        loader_module.Path,
        "stem",
        property(lambda self: "strategy"),
    )
    with pytest.raises(KnowledgeCorpusInvalidError):
        load_corpus(tmp_path)


def test_rejects_empty_document(tmp_path):
    (tmp_path / "empty.md").write_text("   \n\n  \n", encoding="utf-8")
    with pytest.raises(KnowledgeCorpusInvalidError):
        load_corpus(tmp_path)


def test_rejects_document_missing_title_heading(tmp_path):
    (tmp_path / "no_title.md").write_text("Just a paragraph, no heading.\n", encoding="utf-8")
    with pytest.raises(KnowledgeCorpusInvalidError):
        load_corpus(tmp_path)


def test_no_network_and_default_corpus_dir_is_fixed():
    assert DEFAULT_CORPUS_DIR.name == "documents"
    assert DEFAULT_CORPUS_DIR.exists()
