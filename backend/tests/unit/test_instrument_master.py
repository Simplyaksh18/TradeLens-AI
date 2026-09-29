import threading
import time
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.core.exceptions import InstrumentCatalogUnavailableError, InstrumentNotFoundError
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


# ---------------------------------------------------------------------------
# Clean-deploy bootstrap (see CLAUDE.md deployment-compatibility notes --
# app.instruments.master._ensure_loaded/_bootstrap). A fresh production
# filesystem (e.g. Render) has never had refresh() run against it at all.
# No test here touches the real network -- refresh() itself is mocked at the
# InstrumentMaster instance boundary (the same technique InstrumentMaster's
# own public API already exists for, via the existing fetch_fn injection
# point used above), never app.instruments.nse_source directly.
# ---------------------------------------------------------------------------


def _fake_successful_refresh(master: InstrumentMaster):
    """Simulates a real refresh() call using the SAME fixture text every
    other test in this file uses -- proves the bootstrap path loads the
    complete, real catalogue shape, never a hardcoded subset."""

    def _do_refresh(today=None, fetch_fn=None):
        return InstrumentMaster.refresh(master, today=today, fetch_fn=lambda: FIXTURE_TEXT)

    return _do_refresh


def test_case_1_existing_valid_snapshot_loads_without_refresh(tmp_path):
    m1 = InstrumentMaster(tmp_path)
    m1.refresh(today=date(2026, 1, 1), fetch_fn=lambda: FIXTURE_TEXT)

    m2 = InstrumentMaster(tmp_path)
    m2.refresh = Mock(side_effect=AssertionError("refresh() must not be called when a valid snapshot already exists"))

    results = m2.search("RELIANCE")
    assert {r.symbol for r in results} == {"RELIANCE"}
    m2.refresh.assert_not_called()


def test_case_2_missing_snapshot_triggers_exactly_one_automatic_refresh(tmp_path):
    fresh = InstrumentMaster(tmp_path / "clean-deploy")
    fresh.refresh = Mock(side_effect=_fake_successful_refresh(fresh))

    results = fresh.search("RELIANCE")

    assert fresh.refresh.call_count == 1
    assert {r.symbol for r in results} == {"RELIANCE"}
    # the snapshot now exists on disk -- a second InstrumentMaster instance
    # pointed at the same directory can load() it without any refresh at all.
    reloaded = InstrumentMaster(tmp_path / "clean-deploy")
    assert reloaded.load() == 4


def test_case_3_bootstrapped_catalogue_supports_arbitrary_instruments_not_one_hardcoded_symbol(tmp_path):
    fresh = InstrumentMaster(tmp_path / "clean-deploy")
    fresh.refresh = Mock(side_effect=_fake_successful_refresh(fresh))

    # Search first (the exact call the reported production bug went
    # through), then resolve several DIFFERENT symbols from the fixture --
    # proves the fix is global, not specific to whichever symbol happened
    # to trigger the first request.
    fresh.search("a")
    for symbol, provider_symbol in [("RELIANCE", "RELIANCE.NS"), ("TCS", "TCS.NS"), ("TATASTEEL", "TATASTEEL.NS"), ("INFY", "INFY.NS")]:
        assert fresh.resolve(symbol).provider_symbol == provider_symbol
    assert fresh.refresh.call_count == 1  # still exactly one bootstrap for all of the above


def test_case_4_refresh_source_failure_raises_controlled_error_and_fabricates_nothing(tmp_path):
    fresh = InstrumentMaster(tmp_path / "clean-deploy")
    fresh.refresh = Mock(side_effect=ConnectionError("NSE archive unreachable"))

    with pytest.raises(InstrumentCatalogUnavailableError) as exc_info:
        fresh.search("RELIANCE")
    assert isinstance(exc_info.value.__cause__, ConnectionError)
    assert not (tmp_path / "clean-deploy" / "nse_equity_master.csv").exists()

    with pytest.raises(InstrumentCatalogUnavailableError):
        fresh.resolve("RELIANCE")


def test_case_4b_refresh_failure_is_retried_on_a_later_request_not_cached_as_broken(tmp_path):
    fresh = InstrumentMaster(tmp_path / "clean-deploy")
    real_refresh = _fake_successful_refresh(fresh)
    attempts = {"n": 0}

    def _flaky_refresh(today=None, fetch_fn=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ConnectionError("transient")
        return real_refresh(today=today, fetch_fn=fetch_fn)

    # First call fails (transient network error); second call is a real
    # (fixture-backed) successful refresh -- proves a failed bootstrap
    # attempt is not permanently cached as broken for the process lifetime.
    fresh.refresh = Mock(side_effect=_flaky_refresh)

    with pytest.raises(InstrumentCatalogUnavailableError):
        fresh.search("RELIANCE")

    results = fresh.search("RELIANCE")
    assert {r.symbol for r in results} == {"RELIANCE"}
    assert fresh.refresh.call_count == 2


def test_case_5_concurrent_first_access_triggers_at_most_one_refresh(tmp_path):
    fresh = InstrumentMaster(tmp_path / "clean-deploy")
    call_count = {"n": 0}
    call_lock = threading.Lock()

    def _slow_refresh(today=None, fetch_fn=None):
        with call_lock:
            call_count["n"] += 1
        time.sleep(0.05)  # widen the race window so concurrent callers actually overlap
        return _fake_successful_refresh(fresh)()

    fresh.refresh = Mock(side_effect=_slow_refresh)

    errors: list[Exception] = []

    def _worker():
        try:
            fresh.search("RELIANCE")
        except Exception as exc:  # pragma: no cover - failure path, asserted below
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert call_count["n"] == 1


def test_case_6_existing_local_behavior_unchanged_load_without_prior_refresh_still_raises_filenotfounderror(tmp_path):
    # load() itself (as opposed to search()/resolve()'s _ensure_loaded) is
    # UNCHANGED -- it still raises FileNotFoundError directly, exactly as
    # before this deployment-compatibility fix. Only the search()/resolve()
    # path gained automatic bootstrap.
    fresh_master = InstrumentMaster(tmp_path / "empty")
    with pytest.raises(FileNotFoundError):
        fresh_master.load()
