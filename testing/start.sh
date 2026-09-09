#!/bin/bash
# Interactive test session: starts the isolated Postgres cluster, runs Odoo
# in the foreground (Ctrl+C to stop), and guarantees both Odoo and Postgres
# are stopped again afterwards no matter how this script is interrupted
# (Ctrl+C in a terminal, kill -TERM, kill -INT, or a plain crash).
#
# addons_path automatically includes every module folder in this repo's
# root (one level up from testing/), so new modules just need to exist -
# no editing this script.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/.." && pwd)"
ODOO_SRC="${ODOO_SRC:-$HOME/dev/odoo-19}"
DB_NAME="${DB_NAME:-odoo_addons_test}"
HTTP_PORT="${HTTP_PORT:-8069}"

if [ ! -d "$DIR/.venv" ] || [ ! -d "$DIR/.pgdata" ]; then
    echo "Not set up yet - run ./setup.sh first." >&2
    exit 1
fi

ODOO_PID=""
CLEANED_UP=""

cleanup() {
    [ -n "$CLEANED_UP" ] && return
    CLEANED_UP=1
    if [ -n "$ODOO_PID" ] && kill -0 "$ODOO_PID" 2>/dev/null; then
        echo ""
        echo "Stopping Odoo (pid $ODOO_PID)..."
        kill -TERM "$ODOO_PID" 2>/dev/null
        wait "$ODOO_PID" 2>/dev/null
    fi
    echo "Stopping Postgres..."
    "$DIR/pg_stop.sh" || true
}
trap cleanup EXIT INT TERM

"$DIR/pg_start.sh"
source "$DIR/.venv/bin/activate"

ADDONS_PATH="$ODOO_SRC/addons,$ODOO_SRC/odoo/addons,$REPO_ROOT"

echo ""
echo "Odoo starting at http://localhost:$HTTP_PORT  (db: $DB_NAME, login: admin / admin)"
echo "Press Ctrl+C to stop Odoo (Postgres will be stopped automatically after)."
echo ""
python3 "$ODOO_SRC/odoo-bin" \
    --addons-path="$ADDONS_PATH" \
    --db_host="$DIR/.sockets" --db_port=5433 --db_user="$(whoami)" \
    --http-port="$HTTP_PORT" \
    --logfile="$DIR/.logs/odoo.log" \
    -d "$DB_NAME" &
ODOO_PID=$!
wait "$ODOO_PID"
