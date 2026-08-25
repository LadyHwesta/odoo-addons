#!/bin/bash
# Starts the project-local Postgres cluster used for local Odoo testing.
# Fully isolated from any system/Homebrew-managed Postgres: own data dir
# (.pgdata/), own port (5433), own unix socket dir (.sockets/). Never
# registered with `brew services`, so it never auto-starts on login/boot.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PG_PREFIX="$(brew --prefix postgresql@16 2>/dev/null || true)"
if [ -z "$PG_PREFIX" ]; then
    echo "postgresql@16 not found via Homebrew. Install it: brew install postgresql@16" >&2
    exit 1
fi
export PATH="$PG_PREFIX/bin:$PATH"
export LC_ALL="en_US.UTF-8"
# Works around "postmaster became multithreaded during startup" on modern macOS.
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

if [ ! -d "$DIR/.pgdata" ]; then
    echo "No Postgres data directory yet - run ./setup.sh first." >&2
    exit 1
fi
mkdir -p "$DIR/.logs"
pg_ctl -D "$DIR/.pgdata" -l "$DIR/.logs/postgres.log" start
