#!/bin/bash
# Stops the project-local Postgres cluster used for local Odoo testing.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PG_PREFIX="$(brew --prefix postgresql@16 2>/dev/null || true)"
if [ -z "$PG_PREFIX" ]; then
    echo "postgresql@16 not found via Homebrew." >&2
    exit 1
fi
export PATH="$PG_PREFIX/bin:$PATH"
pg_ctl -D "$DIR/.pgdata" stop -m fast
