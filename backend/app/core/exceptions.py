"""Domain-level error hierarchy for market-data access.

These types exist so that yfinance-specific (or any future provider's)
exceptions never leak past the provider boundary. Callers outside
`market_data.providers` must only ever see these types.
"""

from __future__ import annotations


class MarketDataError(Exception):
    """Base class for all TradeLens market-data errors."""


class InstrumentNotFoundError(MarketDataError):
    """Raised when a symbol cannot be resolved in the local instrument master.

    This is a LOCAL determination (the instrument master has no record of the
    symbol) — it is not derived from a provider response.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"Instrument not found in local instrument master: {symbol!r}")


class InstrumentCatalogUnavailableError(MarketDataError):
    """The local instrument-master snapshot does not exist yet AND the
    automatic clean-deploy bootstrap (InstrumentMaster._ensure_loaded --
    see app/instruments/master.py) could not fetch/persist a fresh one
    from the NSE source (network failure, malformed response, or a
    filesystem write failure). Distinct from InstrumentNotFoundError,
    which means the catalogue loaded fine but a specific symbol isn't in
    it. The original exception is preserved via `__cause__`; no
    instrument is ever fabricated in this case."""

    def __init__(self):
        super().__init__(
            "The NSE instrument catalogue is not yet available and could not be bootstrapped from its source. Try again shortly."
        )


class NoDataForPeriodError(MarketDataError):
    """A known-valid instrument returned no bars for the requested period.

    Only raised by MarketDataService, which has already confirmed the
    instrument exists via the instrument master. The provider layer itself
    cannot make this distinction (see EmptyProviderResponseError).
    """

    def __init__(self, provider_symbol: str, start_date, end_date):
        self.provider_symbol = provider_symbol
        self.start_date = start_date
        self.end_date = end_date
        super().__init__(
            f"No data returned for {provider_symbol!r} between {start_date} and {end_date}, "
            "although the instrument is known to the local instrument master."
        )


class EmptyProviderResponseError(MarketDataError):
    """The provider returned an empty result with no distinguishing evidence.

    Raised by the provider layer (e.g. YFinanceProvider) when it receives an
    empty DataFrame without an exception. Deliberately does NOT claim to know
    whether this means an invalid symbol, a genuinely data-less period, or a
    silent throttling response — yfinance does not reliably expose which.
    Callers with extra context (e.g. a validated instrument) may re-classify
    this into a more specific error.
    """

    def __init__(self, provider_symbol: str, start_date, end_date):
        self.provider_symbol = provider_symbol
        self.start_date = start_date
        self.end_date = end_date
        super().__init__(
            f"Provider returned an empty result for {provider_symbol!r} "
            f"({start_date} to {end_date}) with no exception raised. "
            "Cause is not distinguishable from this response alone."
        )


class RateLimitedError(MarketDataError):
    """The provider signaled rate limiting (e.g. yfinance.exceptions.YFRateLimitError)."""


class ProviderUnavailableError(MarketDataError):
    """The provider could not be reached (network/connection-level failure)."""


class MalformedProviderResponseError(MarketDataError):
    """The provider returned data in an unexpected shape (e.g. missing columns)."""


class UnclassifiedProviderError(MarketDataError):
    """An unrecognized provider-side exception occurred.

    Used instead of silently swallowing an exception we don't have a specific
    category for. The original exception is preserved via `__cause__`.
    """


class IndicatorInputInvalidError(MarketDataError):
    """Raised when indicator calculation is requested on a series that fails
    Phase 1B data-quality validation (see app.market_data.validation).

    Indicator functions must never silently compute apparently-legitimate
    values from a dataset already known to contain ERROR-severity issues.
    """

    def __init__(self, provider_symbol: str, error_count: int):
        self.provider_symbol = provider_symbol
        self.error_count = error_count
        super().__init__(
            f"Cannot compute indicators for {provider_symbol!r}: dataset failed "
            f"data-quality validation ({error_count} error(s))."
        )


class StrategyInputInvalidError(MarketDataError):
    """Raised for structural/corrupt Phase 1D strategy input.

    Covers two distinct but equally "not evaluable" failure classes, both of
    which are programming/data-integrity errors rather than legitimate
    strategy outcomes:
      - series-level misalignment (symbol/interval/length/date mismatch
        between the market series and the indicator series);
      - a per-row required numeric value that is non-finite or (for RSI)
        outside its mathematical domain.

    Never raised for indicator warm-up (`None`) — that is the legitimate
    INSUFFICIENT_DATA decision, not an exception.
    """


class OutcomeInputInvalidError(MarketDataError):
    """Raised for structural/corrupt Phase 2A outcome-engine input.

    Covers the same two failure classes as StrategyInputInvalidError, one
    level up the pipeline:
      - series-level misalignment (symbol/interval/length/date mismatch
        between the market series and the strategy evaluation series);
      - a required OHLC value (close/high/low) used in an outcome
        calculation that is non-finite.

    Never raised for an unavailable forward horizon (censored end-of-series
    data) — that is represented by `None` fields on SignalOutcome, not an
    exception.
    """


class BacktestInputInvalidError(MarketDataError):
    """Raised for structural/corrupt Phase 2B backtest input, or config.

    Covers:
      - series-level misalignment (symbol/interval/length/date mismatch
        between the market series and the strategy evaluation series, or
        non-chronological market rows);
      - a required OHLC value (open/close) that is non-finite or non-positive;
      - invalid `BacktestConfig` (non-finite/non-positive initial_capital,
        non-finite/negative transaction_cost/slippage, or a nonzero
        transaction_cost/slippage — Phase 2B V1 defines no cost model to
        apply them, so a nonzero value is rejected explicitly rather than
        silently ignored).

    Never raised for ordinary end-of-data censoring (open position, pending
    entry/exit) — those are represented explicitly on BacktestResult, not
    exceptions.
    """


class AnalyticsInputInvalidError(MarketDataError):
    """Raised for structurally invalid Phase 2C analytics input.

    Covers a `BacktestResult` that cannot support well-defined analytics:
      - an empty equity curve (initial/ending equity would be undefined --
        never invented);
      - non-chronological or duplicate equity-curve dates;
      - a non-finite or negative `cash`/`position_market_value`/`equity`
        value on any equity point;
      - a non-finite trade `net_pnl`/`gross_return`, or non-positive trade
        quantity;
      - a non-finite or non-positive open-position `entry_price`/quantity;
      - a non-finite or non-positive `config.initial_capital`.

    Never raised for "no closed trades" or "no open position" -- those are
    legitimate, explicitly represented states (`None`/`0` fields on
    PerformanceAnalytics), not errors.
    """


class StrategyAuditInputInvalidError(MarketDataError):
    """Raised for structurally invalid Phase 3A audit input.

    Covers:
      - series-level misalignment (symbol/interval/length/date mismatch
        between the market series, the strategy evaluation series, and the
        Phase 2A outcome series; non-chronological or duplicate dates);
      - `audit_date` not present in the aligned series (never silently
        reinterpreted to the nearest trading day);
      - a Phase 2A outcome that cannot be matched to a BUY evaluation at
        the same date;
      - a non-finite forward return on an outcome that point-in-time
        eligibility says should be available, or an eligible outcome
        that's unexpectedly missing/censored (structural inconsistency
        between the supplied market series and outcome series).

    Never raised for ordinary censoring (an outcome not yet eligible as of
    audit_date) -- that is the expected, correct point-in-time state, not
    an error.
    """


class InvestigationInputInvalidError(MarketDataError):
    """Raised for structurally invalid Phase 4 investigation-domain input
    (app.investigation) -- shared by Phase 4A's classification engine,
    Phase 4B's population-comparison engine, Phase 4C's signal-time
    context/association engine, and Phase 4D's composition engine.

    Phase 4A (app.investigation.engine) covers:
      - a `SignalOutcome` whose `decision` is not BUY (Phase 2A's own
        contract guarantees a `SignalOutcome` only exists for a BUY
        evaluation -- anything else reaching Phase 4A is a structural
        inconsistency, not a legitimate NO_SIGNAL/INSUFFICIENT_DATA state);
      - a `SignalOutcome` whose 10-bar horizon fields
        (`forward_close_10d`/`forward_return_10d`/`mae_10d`/`mfe_10d`) are
        only partially present -- Phase 2A's own contract populates all
        four together (a full window) or none at all (censored), so a
        partial set means the supplied outcome is malformed;
      - a non-finite `forward_return_10d` on an outcome that otherwise
        presents a full 10-bar horizon.

    Phase 4B (app.investigation.comparison) covers:
      - an eligible (POSITIVE/NEGATIVE/BREAKEVEN) `SignalInvestigationObservation`
        missing its `forward_return_10d`/`mae_10d`/`mfe_10d`, or presenting
        a non-finite value for one of them (Phase 4A guarantees this for
        output it produces itself, but Phase 4B independently defends its
        own comparison-metric assumptions against a hand-built or
        otherwise-inconsistent `SignalInvestigationDataset`);
      - a `SignalInvestigationDataset` whose declared
        `negative_count`/`positive_count`/`breakeven_count`/
        `unavailable_count`/`total_signal_count` are inconsistent with the
        actual classifications of its own `observations`.

    Phase 4C (app.investigation.context) covers:
      - a symbol/interval mismatch between a Phase 4A
        `SignalInvestigationDataset` and the `OHLCVSeries`/
        `IndicatorSeries` supplied alongside it;
      - a Phase 4A `signal_date` that cannot be resolved against the
        supplied market/indicator series (via the reused Phase 3B
        alignment check -- see app.audit.engine.build_risk_market_context),
        or a market/indicator series that are themselves misaligned;
      - a historical BUY signal whose signal-time regime is not
        BULLISH_TREND, or whose close/sma20/sma50 are missing -- a valid
        `trend_momentum_v1` BUY structurally requires `close > sma20 >
        sma50` at signal time, so anything else reaching Phase 4C is a
        data inconsistency, never silently downgraded to a different
        regime;
      - a historical BUY signal missing RSI14, or whose RSI14 falls
        outside the accepted inclusive `[40, 70]` BUY range;
      - the same population-count-consistency check as Phase 4B, applied
        to the same `SignalInvestigationDataset`.

    Phase 4D (app.investigation.composer) covers:
      - a `provider_symbol`/`interval`/`strategy_id`/`strategy_name`
        mismatch between the Phase 4A/4B/4C inputs being composed;
      - a Phase 4B or Phase 4C population count (`total_signal_count`/
        `eligible_count`/`unavailable_count`/failed-or-non_failed
        population `count`) that disagrees with the Phase 4A-derived
        authoritative counts;
      - a Phase 4C `context_analysis.observations` (signal_date,
        classification) sequence that does not exactly match Phase 4A's
        `investigation_dataset.observations` sequence, in order (missing,
        extra, reordered, or reclassified observations).

    Never raised for an incomplete/censored 10-bar horizon where all four
    fields are legitimately `None` together -- that is the expected
    UNAVAILABLE classification (see app.investigation.models), not an
    error, and UNAVAILABLE observations never enter a Phase 4B/4C
    comparison population summary (though Phase 4C still builds and keeps
    their signal-time context for traceability). Never raised for a
    missing `annualized_realized_volatility_20` (fewer than 21 closes of
    history) -- that is legitimate volatility censoring, not a BUY
    structural requirement.
    """


class AuthError(Exception):
    """Base class for Phase 1G authentication/session errors."""


class EmailAlreadyRegisteredError(AuthError):
    """Registration attempted with an email that already has an account."""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"An account with this email already exists: {email!r}")


class WeakPasswordError(AuthError):
    """Password fails the length policy (see app.auth.security)."""


class InvalidCredentialsError(AuthError):
    """Local login failed. Deliberately generic — never states whether the
    email exists or the password was wrong (avoids account enumeration)."""

    def __init__(self):
        super().__init__("Invalid email or password.")


class InvalidGoogleCredentialError(AuthError):
    """Google ID token failed cryptographic/audience/claim verification."""


class GoogleAccountCollisionError(AuthError):
    """A verified Google sign-in's email matches an existing LOCAL account.

    Safe-by-default policy (see CLAUDE.md Phase 1G): never auto-link, since
    local registration in this phase does not verify email ownership — an
    unverified local account could exist for an email the "local" registrant
    doesn't actually control. Silently linking would let a legitimate Google
    sign-in inherit whatever that pre-existing (unverified) local account is
    attached to. The user is told to sign in locally instead.
    """

    def __init__(self, email: str):
        self.email = email
        super().__init__(
            f"An account with {email!r} already exists. Sign in with your email and password instead."
        )


class SessionInvalidError(AuthError):
    """No valid, unexpired, unrevoked session for the presented cookie."""


class KnowledgeError(Exception):
    """Base class for Phase 5A research knowledge/retrieval errors
    (app.knowledge). Deliberately its own hierarchy, not MarketDataError --
    the knowledge corpus is static reference documentation, not market
    data."""


class KnowledgeCorpusInvalidError(KnowledgeError):
    """Raised by the Phase 5A document loader (app.knowledge.loader) for a
    malformed controlled corpus: a document missing its required leading
    `# Title` heading, an empty document, or a duplicate `document_id`
    across the corpus. The controlled corpus is a fixed, version-controlled
    set of files, so any of these indicate a corpus authoring mistake, not
    a runtime/user condition -- always an explicit failure, never a
    silently-skipped document."""


class EmbeddingInputInvalidError(KnowledgeError):
    """Raised by an EmbeddingProvider (app.knowledge.embedding) for blank
    input text, or if a produced embedding is empty, non-finite, or not of
    the provider's fixed declared dimension."""


class VectorStoreInputInvalidError(KnowledgeError):
    """Raised by a VectorStore (app.knowledge.vector_store) for a vector
    whose dimension does not match the store's established dimension, a
    non-finite vector component, or an invalid `top_k` (< 1)."""


class RetrievalInputInvalidError(KnowledgeError):
    """Raised by ResearchKnowledgeRetriever (app.knowledge.retriever) for a
    blank/whitespace-only query, an invalid `top_k` (< 1), or a retrieve()
    call before the corpus has been indexed."""


class ResearchExplanationError(Exception):
    """Base class for Phase 5B grounded-explanation errors (app.ai).
    Deliberately its own hierarchy -- Phase 5B composes Phase 5A retrieval
    but is a distinct concern (LLM provider orchestration), matching the
    existing precedent of AuthError/KnowledgeError each being self-
    contained rather than everything inheriting MarketDataError."""


class ResearchExplanationInputInvalidError(ResearchExplanationError):
    """Raised by app.ai.service.explain_research_question for a blank/
    whitespace-only question or an invalid `top_k` (< 1) -- validated
    before Phase 5A retrieval is even attempted."""


class MissingProviderConfigurationError(ResearchExplanationError):
    """Raised by GroqResearchLanguageModel when GROQ_API_KEY is not
    configured. Always raised at the moment the provider is actually
    invoked (never at import time), so the rest of the application can
    import app.ai without a configured key -- e.g. all deterministic
    tests, and any future caller that only needs the insufficient-
    evidence path, never touch Groq at all."""


class ProviderRequestFailedError(ResearchExplanationError):
    """Raised by GroqResearchLanguageModel when the underlying Groq SDK
    call fails (network error, malformed response, non-2xx status). Wraps
    the original exception's message only -- never leaks a raw SDK
    exception type or object into the domain layer."""


class ProviderRateLimitedError(ProviderRequestFailedError):
    """Raised by GroqToolCallingLanguageModel specifically for a Groq
    HTTP 429 (rate/quota limit). A subclass of ProviderRequestFailedError
    (not a sibling) so any existing handling of the broader provider-
    failure case still applies; the API layer registers a MORE SPECIFIC
    mapping for this subclass so a genuine rate limit can be distinguished
    from a general provider failure (see CLAUDE.md Phase 5E rate-limit
    diagnosis). Message may include a safe retry-after hint; never the
    Groq API key or raw response headers."""


class AgentInputInvalidError(ResearchExplanationError):
    """Raised by app.agent.agent.run_research_agent for a blank/
    whitespace-only question. Reuses the ResearchExplanationError
    hierarchy (Phase 5C's agent builds directly on Phase 5B's provider
    boundary) rather than starting a third parallel hierarchy."""

