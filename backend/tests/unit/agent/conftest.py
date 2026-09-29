"""Phase 5C test fixtures: deterministic market data (no network), a real
indexed Phase 5A retriever, and scripted fake tool-calling providers so no
test ever touches Groq."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.agent.dependencies import AgentDependencies
from app.agent.models import AgentModelResponse
from app.agent.provider import ToolCallingLanguageModel
from app.instruments.models import Exchange, Instrument, InstrumentStatus, InstrumentType
from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore
from app.market_data.models import OHLCVBar, OHLCVSeries

RELIANCE = Instrument(
    symbol="RELIANCE",
    exchange=Exchange.NSE,
    name="Reliance Industries Limited",
    provider_symbol="RELIANCE.NS",
    instrument_type=InstrumentType.EQUITY,
    status=InstrumentStatus.ACTIVE,
)


class FakeInstrumentMaster:
    def __init__(self, instruments=(RELIANCE,)):
        self._by_symbol = {i.symbol: i for i in instruments}

    def search(self, query: str, limit: int = 20):
        q = query.strip().upper()
        return [i for i in self._by_symbol.values() if q in i.symbol or q in i.name.upper()][:limit]

    def resolve(self, symbol: str) -> Instrument:
        return self._by_symbol[symbol.strip().upper()]


class FakeMarketDataService:
    """Deterministic stand-in for MarketDataService -- no cache, no
    provider, no network. Backed by one pre-built OHLCVSeries covering
    the whole fixture range; `get_history` slices it. Mirrors the real
    service's contract of raising InstrumentNotFoundError for a symbol
    the instrument master doesn't recognize (needed so tool tests can
    genuinely exercise the "unknown symbol" controlled-error path)."""

    def __init__(self, series: OHLCVSeries, known_symbols: frozenset[str] = frozenset({"RELIANCE"})):
        self._series = series
        self._known_symbols = known_symbols
        self.calls: list[tuple] = []

    def get_history(self, symbol: str, interval: str, start_date, end_date, today=None) -> OHLCVSeries:
        from app.core.exceptions import InstrumentNotFoundError

        if symbol.strip().upper() not in self._known_symbols:
            raise InstrumentNotFoundError(symbol)
        self.calls.append((symbol, interval, start_date, end_date))
        return self._series.sliced(start_date, end_date)


def _make_repeating_cycle_series(n_cycles: int = 3, cycle_len: int = 90, start: date = date(2024, 1, 1)) -> OHLCVSeries:
    """Same shape as the accepted Phase 3D/4E test fixtures -- produces
    real BUY/NO_SIGNAL/INSUFFICIENT_DATA signals spread across a long
    series with a natural censored tail."""

    def _cycle_closes():
        closes, close = [], 100.0
        for i in range(cycle_len):
            if i < 50:
                close += 0.01
            elif i < 65:
                close += 3.0
            else:
                close -= 3.0
            closes.append(close)
        return closes

    all_closes = _cycle_closes() * n_cycles
    bars = tuple(
        OHLCVBar(date=start + timedelta(days=i), open=c, high=c + 2, low=c - 2, close=c, adj_close=c, volume=1000)
        for i, c in enumerate(all_closes)
    )
    return OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=bars)


FIXTURE_SERIES = _make_repeating_cycle_series()
FIXTURE_START = FIXTURE_SERIES.bars[0].date.isoformat()
FIXTURE_END = FIXTURE_SERIES.bars[-1].date.isoformat()
# A known BUY date within the fixture (see test_investigations.py's
# documented BUY-index list for this exact fixture shape).
FIXTURE_KNOWN_BUY_DATE = (FIXTURE_SERIES.bars[0].date + timedelta(days=119)).isoformat()


@pytest.fixture
def market_service() -> FakeMarketDataService:
    return FakeMarketDataService(FIXTURE_SERIES)


@pytest.fixture
def instrument_master() -> FakeInstrumentMaster:
    return FakeInstrumentMaster()


@pytest.fixture(scope="module")
def knowledge_retriever() -> ResearchKnowledgeRetriever:
    r = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    r.index_corpus()
    return r


@pytest.fixture
def deps(market_service, instrument_master, knowledge_retriever) -> AgentDependencies:
    return AgentDependencies(
        market_data_service=market_service, instrument_master=instrument_master, knowledge_retriever=knowledge_retriever
    )


class ScriptedToolCallingProvider(ToolCallingLanguageModel):
    """Returns pre-scripted `AgentModelResponse`s in order, one per
    `generate_step` call. Records every call for assertion. Never touches
    the network."""

    def __init__(self, script: list[AgentModelResponse]):
        self._script = list(script)
        self.calls: list[tuple] = []

    def generate_step(self, messages, tools):
        self.calls.append((list(messages), list(tools)))
        if not self._script:
            return AgentModelResponse(final_text="No more scripted responses.")
        return self._script.pop(0)

    @property
    def model_name(self):
        return "scripted-fake"


class FailingToolCallingProvider(ToolCallingLanguageModel):
    def generate_step(self, messages, tools):
        raise RuntimeError("simulated provider failure")

    @property
    def model_name(self):
        return "failing-fake"
