"""Local instrument-master search/lookup. Never queries the provider."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_instrument_master
from app.api.schemas.instruments import InstrumentSchema, InstrumentSearchResponse
from app.instruments.master import InstrumentMaster

router = APIRouter()

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@router.get(
    "/instruments",
    response_model=InstrumentSearchResponse,
    summary="Search the local NSE instrument master by symbol or company name",
)
def search_instruments(
    q: str = Query(..., min_length=1, description="Case-insensitive substring of symbol or company name"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    instrument_master: InstrumentMaster = Depends(get_instrument_master),
) -> InstrumentSearchResponse:
    results = instrument_master.search(q, limit=limit)
    return InstrumentSearchResponse(results=[InstrumentSchema.from_domain(i) for i in results])


@router.get(
    "/instruments/{symbol}",
    response_model=InstrumentSchema,
    summary="Resolve a single NSE instrument by its exact trading symbol",
)
def get_instrument(
    symbol: str,
    instrument_master: InstrumentMaster = Depends(get_instrument_master),
) -> InstrumentSchema:
    instrument = instrument_master.resolve(symbol)
    return InstrumentSchema.from_domain(instrument)
