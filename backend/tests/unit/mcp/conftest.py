"""Phase 5D test fixtures: reuse the exact Phase 5C deterministic fake
dependencies (no network, no Groq) so MCP adapter/protocol tests never
touch yfinance or a real LLM."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from app.agent.dependencies import AgentDependencies
from tests.unit.agent.conftest import (  # noqa: F401 -- reused fixtures
    FIXTURE_END,
    FIXTURE_KNOWN_BUY_DATE,
    FIXTURE_START,
    FakeInstrumentMaster,
    FakeMarketDataService,
    instrument_master,
    knowledge_retriever,
    market_service,
)


@pytest.fixture
def deps(market_service, instrument_master, knowledge_retriever) -> AgentDependencies:
    return AgentDependencies(
        market_data_service=market_service, instrument_master=instrument_master, knowledge_retriever=knowledge_retriever
    )
