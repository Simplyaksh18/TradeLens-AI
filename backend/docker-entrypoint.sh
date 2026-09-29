#!/bin/sh
# Applies pending Alembic migrations against whatever DATABASE_URL points
# to (see app/core/config.py / alembic/env.py — DATABASE_URL is the single
# source of truth, never duplicated in alembic.ini), then starts the app.
# Native development runs `alembic upgrade head` manually; a container gets
# a fresh, unmigrated database on every first run, so this step can't be
# skipped there.
set -e

alembic upgrade head

exec "$@"
