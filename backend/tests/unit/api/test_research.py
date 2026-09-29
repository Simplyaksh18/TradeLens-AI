"""Phase 5E: POST /research route tests. No real Groq, no network --
`get_agent_dependencies`/`get_tool_calling_provider` are overridden with
the exact deterministic Phase 5C fakes/fixtures (`tests/unit/agent/
conftest.py`), so `run_research_agent` runs for real against a scripted
fake provider."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import uuid

from app.agent.dependencies import AgentDependencies
from app.agent.models import AgentModelResponse, ToolCallRequest
from app.api.dependencies import get_agent_dependencies, get_tool_calling_provider
from app.auth.dependencies import get_current_user
from app.auth.models import AuthProvider, User
from app.core.exceptions import (
    AgentInputInvalidError,
    MissingProviderConfigurationError,
    ProviderRateLimitedError,
    ProviderRequestFailedError,
    SessionInvalidError,
)
from app.main import app
from tests.unit.agent.conftest import (
    FIXTURE_END,
    FIXTURE_KNOWN_BUY_DATE,
    FIXTURE_START,
    FIXTURE_SERIES,
    FailingToolCallingProvider,
    FakeInstrumentMaster,
    FakeMarketDataService,
    ScriptedToolCallingProvider,
)
from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore


@pytest.fixture(scope="module")
def _knowledge_retriever() -> ResearchKnowledgeRetriever:
    r = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    r.index_corpus()
    return r


@pytest.fixture
def deps(_knowledge_retriever) -> AgentDependencies:
    return AgentDependencies(
        market_data_service=FakeMarketDataService(FIXTURE_SERIES),
        instrument_master=FakeInstrumentMaster(),
        knowledge_retriever=_knowledge_retriever,
    )


_FAKE_USER = User(
    id=uuid.uuid4(),
    email="researcher@example.com",
    full_name="Test Researcher",
    display_name="Test Researcher",
    auth_provider=AuthProvider.LOCAL,
)


def _client(deps, provider, *, authenticated: bool = True) -> TestClient:
    # Post-5F hardening: /research now requires the same
    # get_current_user dependency every other protected TradeLens
    # endpoint uses. Authenticated by default here so the pre-existing
    # Phase 5E test matrix below keeps testing agent/tool-calling
    # behavior, not auth -- the dedicated auth tests below override this.
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    else:
        def _raise_session_invalid():
            raise SessionInvalidError()

        app.dependency_overrides[get_current_user] = _raise_session_invalid
    app.dependency_overrides[get_agent_dependencies] = lambda: deps
    app.dependency_overrides[get_tool_calling_provider] = lambda: provider
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _final_answer_provider(text="Grounded answer.") -> ScriptedToolCallingProvider:
    return ScriptedToolCallingProvider([AgentModelResponse(final_text=text)])


# ---------------------------------------------------------------------------
# 1-2: valid request returns a structured result; blank question rejected
# ---------------------------------------------------------------------------


def test_valid_research_request_returns_structured_result(deps):
    client = _client(deps, _final_answer_provider())
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "What are the exact BUY conditions?"
    assert body["answer"] == "Grounded answer."
    assert body["stopped_reason"] == "final_answer"
    assert body["completed_steps"] == 0
    assert body["tool_trace"] == []
    assert body["knowledge_sources"] == []


def test_blank_question_rejected(deps):
    client = _client(deps, _final_answer_provider())
    response = client.post("/api/v1/research", json={"question": "   "})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 3: overly long question rejected
# ---------------------------------------------------------------------------


def test_overly_long_question_rejected(deps):
    client = _client(deps, _final_answer_provider())
    response = client.post("/api/v1/research", json={"question": "x" * 2001})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 4: post-Phase-5F hardening -- /research now REQUIRES authentication,
# deliberately UNLIKE the other research endpoints (see CLAUDE.md post-5F
# hardening: this is the only endpoint that spends real Groq quota).
# ---------------------------------------------------------------------------


def test_unauthenticated_request_rejected_with_existing_session_invalid_convention(deps):
    client = _client(deps, _final_answer_provider(), authenticated=False)
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"


def test_authenticated_request_accepted(deps):
    client = _client(deps, _final_answer_provider(), authenticated=True)
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert response.status_code == 200


def test_groq_not_called_when_authentication_fails(deps):
    provider = _final_answer_provider()
    client = _client(deps, provider, authenticated=False)
    client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert len(provider.calls) == 0  # the route body (and thus run_research_agent) never executed


def test_no_credentials_exposed_in_unauthenticated_error_body(deps):
    client = _client(deps, _final_answer_provider(), authenticated=False)
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert "gsk_" not in response.text
    assert "Traceback" not in response.text


# ---------------------------------------------------------------------------
# 5-6: Phase 5C agent called exactly once; route never calls Groq directly
# ---------------------------------------------------------------------------


def test_agent_called_exactly_once_per_request(deps):
    provider = _final_answer_provider()
    client = _client(deps, provider)
    client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert len(provider.calls) == 1  # one generate_step call = one agent loop iteration reaching final_text


def test_route_module_never_imports_groq_sdk_directly():
    import ast
    from pathlib import Path

    source = Path("app/api/routes/research.py").read_text()
    tree = ast.parse(source)
    imported_names = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported_names |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "groq" not in imported_names


# ---------------------------------------------------------------------------
# 7-9: tool trace / knowledge provenance / audit structure serialized correctly
# ---------------------------------------------------------------------------


def test_tool_trace_serialized_correctly(deps):
    provider = ScriptedToolCallingProvider(
        [
            AgentModelResponse(
                final_text=None,
                tool_calls=(ToolCallRequest(tool_call_id="1", tool_name="search_instruments", arguments={"query": "RELIANCE"}),),
            ),
            AgentModelResponse(final_text="Found it."),
        ]
    )
    client = _client(deps, provider)
    response = client.post("/api/v1/research", json={"question": "Find RELIANCE."})
    body = response.json()
    assert len(body["tool_trace"]) == 1
    entry = body["tool_trace"][0]
    assert entry["tool_name"] == "search_instruments"
    assert entry["status"] == "ok"
    assert entry["arguments"] == {"query": "RELIANCE"}
    assert entry["raw_result"]["results"][0]["symbol"] == "RELIANCE"


def test_knowledge_provenance_serialized_correctly(deps):
    provider = ScriptedToolCallingProvider(
        [
            AgentModelResponse(
                final_text=None,
                tool_calls=(
                    ToolCallRequest(tool_call_id="1", tool_name="search_research_knowledge", arguments={"query": "BUY conditions"}),
                ),
            ),
            AgentModelResponse(final_text="Here is the rule."),
        ]
    )
    client = _client(deps, provider)
    response = client.post("/api/v1/research", json={"question": "What triggers a BUY?"})
    body = response.json()
    assert len(body["knowledge_sources"]) > 0
    source = body["knowledge_sources"][0]
    for key in ("document_id", "document_title", "source_path", "chunk_id", "chunk_ordinal", "section_heading", "trust"):
        assert key in source


def test_audit_evidence_structure_preserved_in_response(deps):
    provider = ScriptedToolCallingProvider(
        [
            AgentModelResponse(
                final_text=None,
                tool_calls=(
                    ToolCallRequest(
                        tool_call_id="1",
                        tool_name="audit_strategy_decision",
                        arguments={"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END},
                    ),
                ),
            ),
            AgentModelResponse(final_text="Audited."),
        ]
    )
    client = _client(deps, provider)
    response = client.post("/api/v1/research", json={"question": "Audit RELIANCE."})
    raw = response.json()["tool_trace"][0]["raw_result"]
    for key in ("decision", "decision_evidence", "point_in_time_context", "retrospective_hindsight"):
        assert key in raw
    assert "regime" not in raw  # never flattened back -- stays nested under point_in_time_context


# ---------------------------------------------------------------------------
# 10-12: provider failure / missing config / step-limit mapped safely
# ---------------------------------------------------------------------------


def test_provider_failure_safely_mapped(deps):
    # FailingToolCallingProvider raises a plain, unmapped RuntimeError --
    # simulating a provider failure outside the accepted
    # MissingProviderConfigurationError/ProviderRequestFailedError
    # hierarchy (the real GroqToolCallingLanguageModel always wraps SDK
    # failures into ProviderRequestFailedError, see app.agent.provider).
    # raise_server_exceptions=False exercises Starlette's own default
    # handler, matching real production behavior: a generic, safe 500
    # with no traceback in the body.
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    app.dependency_overrides[get_agent_dependencies] = lambda: deps
    app.dependency_overrides[get_tool_calling_provider] = lambda: FailingToolCallingProvider()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert response.status_code == 500
    assert "Traceback" not in response.text
    assert "simulated provider failure" not in response.text


class _MissingConfigProvider:
    model_name = "unconfigured"

    def generate_step(self, messages, tools):
        raise MissingProviderConfigurationError("GROQ_API_KEY is not configured.")


def test_missing_provider_config_safely_mapped(deps):
    client = _client(deps, _MissingConfigProvider())
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PROVIDER_NOT_CONFIGURED"


class _RequestFailedProvider:
    model_name = "flaky"

    def generate_step(self, messages, tools):
        raise ProviderRequestFailedError("Groq tool-calling request failed: simulated.")


def test_provider_request_failed_safely_mapped(deps):
    client = _client(deps, _RequestFailedProvider())
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_PROVIDER_REQUEST_FAILED"


class _RateLimitedProvider:
    model_name = "throttled"

    def generate_step(self, messages, tools):
        raise ProviderRateLimitedError("Groq rate/quota limit reached. Retry after approximately 30 seconds.")


def test_provider_rate_limited_maps_to_distinct_429_not_generic_502(deps):
    # See CLAUDE.md Phase 5E rate-limit diagnosis: a genuine Groq 429 must
    # be distinguishable from a general provider failure (502).
    client = _client(deps, _RateLimitedProvider())
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    assert response.status_code == 429
    body = response.json()
    assert body["error"]["code"] == "AI_PROVIDER_RATE_LIMITED"
    assert "gsk_" not in response.text


def test_agent_step_limit_reached_returns_200_with_controlled_answer(deps):
    always_tool_call = AgentModelResponse(
        final_text=None, tool_calls=(ToolCallRequest(tool_call_id="1", tool_name="search_instruments", arguments={"query": "RELIANCE"}),)
    )
    provider = ScriptedToolCallingProvider([always_tool_call] * 10)
    client = _client(deps, provider)
    response = client.post("/api/v1/research", json={"question": "Keep searching forever."})
    assert response.status_code == 200
    body = response.json()
    assert body["stopped_reason"] == "max_steps_reached"
    assert body["completed_steps"] == 5  # MAX_TOOL_STEPS, never exceeded


# ---------------------------------------------------------------------------
# 13: no secret leakage in error body
# ---------------------------------------------------------------------------


def test_no_secret_leakage_in_provider_error_body(deps):
    client = _client(deps, _MissingConfigProvider())
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    text = response.text
    assert "gsk_" not in text
    assert "Traceback" not in text


# ---------------------------------------------------------------------------
# 14: question preserved exactly to the agent
# ---------------------------------------------------------------------------


def test_question_preserved_exactly_to_agent(deps):
    provider = _final_answer_provider()
    client = _client(deps, provider)
    question = "Audit RELIANCE on 2024-06-13 and explain the decision."
    client.post("/api/v1/research", json={"question": question})
    sent_messages = provider.calls[0][0]
    user_message = next(m for m in sent_messages if m.role == "user")
    assert user_message.content == question


# ---------------------------------------------------------------------------
# 15: response model rejects/does not expose unexpected internal fields
# ---------------------------------------------------------------------------


def test_response_does_not_expose_unexpected_internal_fields(deps):
    client = _client(deps, _final_answer_provider())
    response = client.post("/api/v1/research", json={"question": "What are the exact BUY conditions?"})
    body = response.json()
    assert set(body.keys()) == {"question", "answer", "stopped_reason", "completed_steps", "tool_trace", "knowledge_sources", "model"}
