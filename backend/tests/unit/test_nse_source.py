from pathlib import Path

from app.instruments.models import Exchange, InstrumentStatus, InstrumentType
from app.instruments.nse_source import parse_nse_equity_csv

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "nse_equity_sample.csv").read_text()


def test_parses_expected_instrument_count():
    instruments = parse_nse_equity_csv(FIXTURE)
    assert len(instruments) == 4


def test_parses_fields_and_provider_symbol_mapping():
    instruments = parse_nse_equity_csv(FIXTURE)
    reliance = next(i for i in instruments if i.symbol == "RELIANCE")

    assert reliance.name == "Reliance Industries Limited"
    assert reliance.provider_symbol == "RELIANCE.NS"
    assert reliance.exchange == Exchange.NSE
    assert reliance.instrument_type == InstrumentType.EQUITY
    assert reliance.status == InstrumentStatus.ACTIVE
    assert reliance.isin == "INE002A01018"
    assert reliance.series == "EQ"


def test_handles_whitespace_in_header_and_symbol_casing():
    # header has leading spaces on all but the first two columns (real NSE quirk)
    instruments = parse_nse_equity_csv(FIXTURE)
    symbols = {i.symbol for i in instruments}
    assert symbols == {"RELIANCE", "INFY", "TCS", "TATASTEEL"}
