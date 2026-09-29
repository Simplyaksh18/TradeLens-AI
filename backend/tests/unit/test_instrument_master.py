from datetime import date
from pathlib import Path

import pytest

from app.core.exceptions import InstrumentNotFoundError
from app.instruments.master import InstrumentMaster

FIXTURE_TEXT = (Path(__file__).parent.parent / "fixtures" / "nse_equity_sample.csv").read_text()


@pytest.fixture
def master(tmp_path) -> InstrumentMaster:
    m = InstrumentMaster(tmp_path)
    m.refresh(today=date(2026, 1, 1), fetch_fn=lambda: FIXTURE_TEXT)
    return m


def test_refresh_persists_snapshot_to_disk(tmp_path, master):
    assert (tmp_path / "nse_equity_master.csv").exists()
    assert (tmp_path / "nse_equity_master.meta.json").exists()


def test_resolve_exact_symbol_case_insensitive(master):
    instrument = master.resolve("reliance")
    assert instrument.symbol == "RELIANCE"
    assert instrument.provider_symbol == "RELIANCE.NS"


def test_resolve_unknown_symbol_raises(master):
    with pytest.raises(InstrumentNotFoundError):
        master.resolve("NOTREAL")


def test_search_by_partial_company_name(master):
    results = master.search("tata")
    symbols = {r.symbol for r in results}
    assert symbols == {"TCS", "TATASTEEL"}


def test_search_by_partial_symbol(master):
    results = master.search("REL")
    assert {r.symbol for r in results} == {"RELIANCE"}


def test_load_without_prior_refresh_raises(tmp_path):
    fresh_master = InstrumentMaster(tmp_path / "empty")
    with pytest.raises(FileNotFoundError):
        fresh_master.load()


def test_load_reads_persisted_snapshot_without_refetching(tmp_path):
    m1 = InstrumentMaster(tmp_path)
    m1.refresh(today=date(2026, 1, 1), fetch_fn=lambda: FIXTURE_TEXT)

    m2 = InstrumentMaster(tmp_path)
    count = m2.load()

    assert count == 4
    assert m2.resolve("INFY").provider_symbol == "INFY.NS"
