# TradeLens backend — FastAPI served by Uvicorn.
#
# Build context is backend/ (see compose.yaml). Directory depth under
# /app/backend deliberately mirrors the native repo layout (backend/app/api/
# dependencies.py three levels below the repo root) so
# `Path(__file__).resolve().parents[3]` in app/api/dependencies.py still
# resolves to /app — where the persistent data volume is mounted — without
# any code change.
FROM python:3.13-slim

WORKDIR /app/backend

# Dependencies first so `docker build` only reinstalls them when
# requirements.txt actually changes, not on every source edit.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

# Non-root runtime user. /app/data is where InstrumentMaster and
# HistoricalDataCache read/write (see app/api/dependencies.py) — created and
# owned by appuser up front so it's writable even before a volume is mounted
# over it (Docker preserves the mount point's existing ownership).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=3)" || exit 1

# Entrypoint applies Alembic migrations (a container starts from a fresh,
# unmigrated database every first run, unlike native dev where `alembic
# upgrade head` is a one-time manual step) before exec-ing the CMD below.
# No --reload: this is the production-style container command. Native
# development keeps using `uvicorn app.main:app --reload` directly.
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
