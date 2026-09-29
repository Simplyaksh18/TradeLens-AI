import importlib

import pytest


def test_openapi_exposes_expected_routes():
    from app.main import app

    paths = app.openapi()["paths"]
    for expected in (
        "/api/v1/health",
        "/api/v1/instruments",
        "/api/v1/instruments/{symbol}",
        "/api/v1/market-data/{symbol}",
        "/api/v1/indicators/{symbol}",
        "/api/v1/strategies/trend-momentum-v1/{symbol}",
    ):
        assert expected in paths


def test_docs_and_openapi_json_available():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_importing_main_module_causes_zero_network_calls(monkeypatch):
    import requests
    import yfinance as yf

    import app.main as main_module

    def _explode(*_args, **_kwargs):
        raise AssertionError("network call attempted while importing app.main")

    monkeypatch.setattr(requests, "get", _explode)
    monkeypatch.setattr(yf, "download", _explode)

    importlib.reload(main_module)


def test_dependency_construction_causes_zero_network_calls(monkeypatch):
    import requests
    import yfinance as yf

    from app.api import dependencies as deps

    def _explode(*_args, **_kwargs):
        raise AssertionError("network call attempted during dependency construction")

    monkeypatch.setattr(requests, "get", _explode)
    monkeypatch.setattr(yf, "download", _explode)

    deps.get_instrument_master.cache_clear()
    deps.get_cache.cache_clear()
    deps.get_provider.cache_clear()
    try:
        deps.get_instrument_master()
        deps.get_cache()
        deps.get_provider()
    finally:
        deps.get_instrument_master.cache_clear()
        deps.get_cache.cache_clear()
        deps.get_provider.cache_clear()


def test_testclient_startup_causes_zero_network_calls(monkeypatch):
    import requests
    import yfinance as yf
    from fastapi.testclient import TestClient

    from app.main import app

    def _explode(*_args, **_kwargs):
        raise AssertionError("network call attempted during TestClient startup/health request")

    monkeypatch.setattr(requests, "get", _explode)
    monkeypatch.setattr(yf, "download", _explode)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
