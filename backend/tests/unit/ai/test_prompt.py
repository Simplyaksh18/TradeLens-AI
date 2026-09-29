"""Phase 5B: grounded prompt construction tests."""

from __future__ import annotations

from app.ai.prompt import SYSTEM_INSTRUCTION, build_user_prompt


def _chunks(retriever, question):
    return [r.chunk for r in retriever.retrieve(question, top_k=3)]


def test_deterministic_for_same_inputs(retriever):
    chunks = _chunks(retriever, "What conditions trigger Trend + Momentum v1?")
    a = build_user_prompt("What conditions trigger Trend + Momentum v1?", chunks)
    b = build_user_prompt("What conditions trigger Trend + Momentum v1?", chunks)
    assert a == b


def test_prompt_contains_question_and_delimiters(retriever):
    question = "What conditions trigger Trend + Momentum v1?"
    chunks = _chunks(retriever, question)
    prompt = build_user_prompt(question, chunks)
    assert "USER QUESTION" in prompt
    assert "AUTHORITATIVE TRADELENS CONTEXT" in prompt
    assert question in prompt


def test_prompt_contains_expected_chunk_content_and_provenance(retriever):
    question = "What conditions trigger Trend + Momentum v1?"
    chunks = _chunks(retriever, question)
    prompt = build_user_prompt(question, chunks)
    for chunk in chunks:
        assert chunk.content in prompt
        assert chunk.source.chunk_id in prompt
        assert chunk.source.document_title in prompt


def test_prompt_preserves_retrieval_order(retriever):
    question = "What conditions trigger Trend + Momentum v1?"
    chunks = _chunks(retriever, question)
    prompt = build_user_prompt(question, chunks)
    positions = [prompt.index(chunk.source.chunk_id) for chunk in chunks]
    assert positions == sorted(positions)


def test_system_instruction_states_all_required_boundary_rules():
    required_phrases = [
        "explaining TradeLens research methodology",
        "Use ONLY the supplied authoritative context",
        "Do not invent missing methodology",
        "does not establish",
        "Do not perform new financial calculations",
        "Do not provide personalized investment advice",
        "proves causation",
        "predict",
        "point-in-time",
        "retrospective",
        "Do not invent citations",
        "deferred",
    ]
    for phrase in required_phrases:
        assert phrase.lower() in SYSTEM_INSTRUCTION.lower(), f"missing required rule text: {phrase!r}"


def test_system_instruction_establishes_question_as_untrusted():
    assert "untrusted" in SYSTEM_INSTRUCTION.lower()
    assert "override" in SYSTEM_INSTRUCTION.lower()
