"""Environment-driven configuration.

Deliberately plain `os.environ` reads rather than adding `pydantic-settings`
as a new dependency — the surface here is small enough not to need it.

No network/filesystem I/O happens at import time: reading `os.environ` is
process-local and instantaneous, matching the existing "zero I/O at import"
contract for `app.main`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Loads backend/.env into os.environ if present (local dev convenience;
# gitignored, never committed). Production deployments set real environment
# variables directly and don't need a .env file. This is the only file
# system access config.py performs, and it's a simple local read, not a
# network call.
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # SQLAlchemy connection string, e.g.
    # postgresql+psycopg://tradelens:password@localhost:5432/tradelens
    # Falls back to a local SQLite file so the app/tests can still boot
    # without a configured Postgres instance; production deployments MUST
    # set DATABASE_URL explicitly.
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./tradelens_dev.db")

    # Set ENVIRONMENT=production to enable the `Secure` cookie flag (requires
    # HTTPS). Local development over plain http intentionally leaves it off.
    environment: str = os.environ.get("ENVIRONMENT", "development")

    session_cookie_name: str = os.environ.get("SESSION_COOKIE_NAME", "tradelens_session")
    session_ttl_days: int = int(os.environ.get("SESSION_TTL_DAYS", "14"))

    google_client_id: str | None = os.environ.get("GOOGLE_CLIENT_ID")

    # Phase 5B -- server-side only. Never read by, or exposed to, frontend
    # code (no VITE_* equivalent exists or should ever exist for this).
    # Deliberately `None` (not a placeholder string) when unset, so
    # GroqResearchLanguageModel can raise an explicit
    # MissingProviderConfigurationError instead of sending a request with
    # a blank/garbage credential.
    groq_api_key: str | None = os.environ.get("GROQ_API_KEY")
    groq_model: str = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    # Post-Phase-5F hardening -- explicit, documented provider selection
    # for Phase 5A knowledge retrieval (see CLAUDE.md post-5F hardening
    # and app.knowledge.embedding.SemanticEmbeddingProvider). "semantic"
    # (the default) uses the real fastembed/ONNX model; "lexical" uses the
    # original deterministic LocalHashEmbeddingProvider (still used
    # unconditionally by every deterministic unit test, regardless of this
    # setting). This is never silently overridden -- if "semantic" is
    # selected but the model fails to load, that is a startup error, not a
    # silent downgrade to lexical retrieval.
    research_embedding_provider: str = os.environ.get("RESEARCH_EMBEDDING_PROVIDER", "semantic")

    # Persistent directory the semantic embedding model is downloaded to
    # once and cached in (never re-downloaded per request/process start
    # once populated). Defaults under the same `data/` directory already
    # bind-mounted into the backend Docker container alongside the
    # instrument-master/market-data caches.
    embedding_model_cache_dir: str = os.environ.get(
        "EMBEDDING_MODEL_CACHE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "embedding_model_cache"),
    )

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"


settings = Settings()
