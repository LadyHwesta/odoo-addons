#!/bin/bash
# One-time setup: creates the Python venv and initializes a project-local
# Postgres cluster, both self-contained inside testing/ (gitignored, never
# committed). Safe to re-run - skips steps that are already done.
#
# Requires:
#   - Homebrew's postgresql@16 (`brew install postgresql@16`)
#   - The Odoo 19 source checked out somewhere, referenced via $ODOO_SRC
#     (default: ~/dev/odoo-19). This repo only holds our own modules -
#     Odoo core is a separate, external clone of github.com/odoo/odoo.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ODOO_SRC="${ODOO_SRC:-$HOME/dev/odoo-19}"

if [ ! -f "$ODOO_SRC/odoo-bin" ]; then
    echo "Odoo 19 source not found at $ODOO_SRC/odoo-bin" >&2
    echo "Clone it first (git clone --branch 19.0 --single-branch --depth 1 https://github.com/odoo/odoo.git \"$ODOO_SRC\")" >&2
    echo "or point ODOO_SRC at an existing checkout." >&2
    exit 1
fi

PG_PREFIX="$(brew --prefix postgresql@16 2>/dev/null || true)"
if [ -z "$PG_PREFIX" ]; then
    echo "postgresql@16 not found via Homebrew. Install it: brew install postgresql@16" >&2
    exit 1
fi
export PATH="$PG_PREFIX/bin:$PATH"

if [ ! -d "$DIR/.venv" ]; then
    echo "Creating venv..."
    python3 -m venv "$DIR/.venv"
fi
source "$DIR/.venv/bin/activate"
pip install --upgrade pip wheel setuptools >/dev/null
echo "Installing Odoo's Python dependencies (this can take a few minutes)..."
pip install -r "$ODOO_SRC/requirements.txt"

if [ ! -d "$DIR/.pgdata" ]; then
    echo "Initializing Postgres data directory..."
    LC_ALL="en_US.UTF-8" initdb --locale=en_US.UTF-8 -E UTF-8 -A trust -D "$DIR/.pgdata"
    mkdir -p "$DIR/.sockets"
    {
        echo "port = 5433"
        echo "unix_socket_directories = '$DIR/.sockets'"
        echo "listen_addresses = 'localhost'"
    } >> "$DIR/.pgdata/postgresql.conf"
fi

mkdir -p "$DIR/.logs"
echo ""
echo "Setup complete. Run ./start.sh to launch Odoo."
