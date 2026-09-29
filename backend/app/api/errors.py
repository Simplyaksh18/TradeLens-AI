"""Central domain-error -> HTTP mapping.

One stable error body shape for every failure:

    {"error": {"code": "...", "message": "..."}}

Never exposes tracebacks, exception class names, filesystem paths, cache
paths, or yfinance-specific details — messages come from the domain
exceptions themselves, which already avoid those (see core/exceptions.py).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import (
    AgentInputInvalidError,
    AnalyticsInputInvalidError,
    BacktestInputInvalidError,
    EmailAlreadyRegisteredError,
    EmptyProviderResponseError,
    GoogleAccountCollisionError,
    IndicatorInputInvalidError,
    InstrumentCatalogUnavailableError,
    InstrumentNotFoundError,
    InvalidCredentialsError,
    InvalidGoogleCredentialError,
    InvestigationInputInvalidError,
    KnowledgeError,
    MalformedProviderResponseError,
    MissingProviderConfigurationError,
    NoDataForPeriodError,
    OutcomeInputInvalidError,
    ProviderRateLimitedError,
    ProviderRequestFailedError,
    ProviderUnavailableError,
    RateLimitedError,
    SessionInvalidError,
    StrategyAuditInputInvalidError,
    StrategyInputInvalidError,
    UnclassifiedProviderError,
    WeakPasswordError,
)


class RequestContractError(Exception):
    """A request-contract violation this API validates itself (date range,
    interval, etc.) — distinct from FastAPI/Pydantic's own
    RequestValidationError, but mapped to the same stable 422 shape."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# Domain exception -> (HTTP status, stable API error code).
#
# IndicatorInputInvalidError/StrategyInputInvalidError map to 500: they mean
# a value/dataset reached indicator or strategy code in a state it should
# never be in (non-finite value, or data that already failed Phase 1B
# validation) — an internal data-integrity contract failure, not an
# ordinary user request mistake and not a legitimate BUY/NO_SIGNAL/
# INSUFFICIENT_DATA trading outcome.
#
# EmptyProviderResponseError is mapped defensively: MarketDataService always
# reclassifies it into NoDataForPeriodError before it could reach a route,
# but if that ever changed, treating it as an upstream anomaly (502) rather
# than crashing unhandled is the safer default.
_DOMAIN_ERROR_MAP: dict[type[Exception], tuple[int, str]] = {
    InstrumentNotFoundError: (404, "INSTRUMENT_NOT_FOUND"),
    # The instrument-master snapshot could not be bootstrapped on a clean
    # filesystem (see app.instruments.master's clean-deploy bootstrap) --
    # a transient upstream/network condition, same reasoning as
    # ProviderUnavailableError below, never an ordinary user mistake.
    InstrumentCatalogUnavailableError: (503, "INSTRUMENT_CATALOG_UNAVAILABLE"),
    NoDataForPeriodError: (404, "NO_DATA_FOR_PERIOD"),
    RateLimitedError: (503, "PROVIDER_RATE_LIMITED"),
    ProviderUnavailableError: (503, "PROVIDER_UNAVAILABLE"),
    MalformedProviderResponseError: (502, "UPSTREAM_PROVIDER_ERROR"),
    UnclassifiedProviderError: (502, "UPSTREAM_PROVIDER_ERROR"),
    EmptyProviderResponseError: (502, "UPSTREAM_PROVIDER_ERROR"),
    IndicatorInputInvalidError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    StrategyInputInvalidError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    # Phase 2A/2B/2C domain-contract failures (Phase 2D). Same reasoning as
    # Strategy/IndicatorInputInvalidError above: these mean a structurally
    # invalid value reached an already-aligned pipeline stage, never an
    # ordinary user request mistake. User-facing input (initial_capital) is
    # validated at the API layer (RequestContractError, 422) before it ever
    # reaches these engines -- see app.api.dependencies.backtest_query_params.
    OutcomeInputInvalidError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    BacktestInputInvalidError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    AnalyticsInputInvalidError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    # Phase 3A/3B/3C (Phase 3D). The route validates audit_date presence
    # itself (RequestContractError, 422) before calling the domain layer,
    # so this is a defense-in-depth backstop for a genuine internal
    # contract violation, not the normal path for a user-picked
    # weekend/out-of-range audit_date.
    StrategyAuditInputInvalidError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    # Phase 4A/4B/4C/4D (Phase 4E). Same reasoning as
    # OutcomeInputInvalidError/StrategyAuditInputInvalidError above: this
    # means a structurally invalid value reached an already-validated
    # investigation-domain stage -- an internal contract failure, never an
    # ordinary user request mistake and never a legitimate empty/censored
    # investigation result (those are represented explicitly, not as
    # errors).
    InvestigationInputInvalidError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    # Phase 5E research API, over the accepted Phase 5C agent.
    # AgentInputInvalidError: defense-in-depth only -- the route's own
    # ResearchQuestionRequest already rejects a blank/whitespace-only
    # question at 422 before the agent is ever called; this exists only
    # in case that guard is ever bypassed.
    AgentInputInvalidError: (422, "INVALID_RESEARCH_QUESTION"),
    # MissingProviderConfigurationError/ProviderRequestFailedError: the
    # Groq provider is unavailable/misconfigured or a live request to it
    # failed -- an upstream/provider problem, not a client mistake and
    # not TradeLens's own deterministic engines failing, so 503/502
    # (matching the existing provider-unavailable/upstream-error
    # reasoning above) rather than 500 or 422.
    MissingProviderConfigurationError: (503, "AI_PROVIDER_NOT_CONFIGURED"),
    # ProviderRateLimitedError is a SUBCLASS of ProviderRequestFailedError
    # (see core/exceptions.py) -- Starlette's exception-handler lookup
    # walks the exception's MRO and picks the most specific registered
    # type, so a genuine Groq 429 is mapped here (429, distinguishable)
    # rather than falling through to the generic 502 entry below.
    ProviderRateLimitedError: (429, "AI_PROVIDER_RATE_LIMITED"),
    ProviderRequestFailedError: (502, "AI_PROVIDER_REQUEST_FAILED"),
    # KnowledgeError: Phase 5A retrieval failure. Tool-level knowledge
    # errors are already caught and returned as ToolResult(status="error")
    # inside app.agent.tools and never raised past the agent loop -- this
    # mapping is a defensive backstop only, for the (effectively
    # unreachable in normal operation) case of the shared knowledge index
    # itself failing to build.
    KnowledgeError: (500, "INTERNAL_DATA_CONTRACT_ERROR"),
    # Auth (Phase 1G). InvalidCredentialsError/SessionInvalidError are
    # deliberately generic (401) — never reveal which check failed, to avoid
    # account/session enumeration.
    EmailAlreadyRegisteredError: (409, "EMAIL_ALREADY_REGISTERED"),
    WeakPasswordError: (422, "WEAK_PASSWORD"),
    InvalidCredentialsError: (401, "INVALID_CREDENTIALS"),
    InvalidGoogleCredentialError: (401, "INVALID_GOOGLE_CREDENTIAL"),
    GoogleAccountCollisionError: (409, "GOOGLE_ACCOUNT_COLLISION"),
    SessionInvalidError: (401, "SESSION_INVALID"),
}


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def register_exception_handlers(app: FastAPI) -> None:
    for exc_type, (status_code, code) in _DOMAIN_ERROR_MAP.items():
        app.add_exception_handler(exc_type, _make_domain_handler(status_code, code))

    @app.exception_handler(RequestContractError)
    async def _request_contract_handler(request: Request, exc: RequestContractError) -> JSONResponse:
        return _error_response(422, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(422, "REQUEST_VALIDATION_ERROR", "Invalid request parameters.")


class UnhandledExceptionSafetyMiddleware(BaseHTTPMiddleware):
    """Deployment-compatibility backstop (see CLAUDE.md).

    Registering a handler for the bare `Exception`/500 type via
    `@app.exception_handler` does NOT work for this: Starlette's own
    `build_middleware_stack` special-cases that key and wires it to
    `ServerErrorMiddleware`, which sits OUTSIDE (before) `CORSMiddleware` in
    the stack -- so a response produced that way never passes back through
    CORSMiddleware and arrives at the browser with no
    `Access-Control-Allow-Origin` header. The browser then reports the
    request to the frontend as an opaque, indistinguishable-from-offline
    network failure (`fetch()` itself rejects) instead of a real, readable
    5xx response -- this was the actual root cause of the misleading
    "Could not reach the TradeLens API." message for the production
    instrument-catalog bug this deployment-compatibility pass fixes.

    This middleware is registered (see app.main) so that it sits BETWEEN
    CORSMiddleware and the router/ExceptionMiddleware. Any exception that
    reaches it (i.e. one not already mapped to a domain handler above) is
    converted to a plain JSONResponse HERE, before it can escape past
    CORSMiddleware — so the response still gets CORS headers applied on its
    way back out. Never exposes a traceback/exception class name/internal
    path, matching every other handler in this file.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            return _error_response(500, "INTERNAL_SERVER_ERROR", "An unexpected server error occurred.")


def _make_domain_handler(status_code: int, code: str):
    async def _handler(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(status_code, code, str(exc))

    return _handler
