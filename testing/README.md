# Local test instance

A self-contained Odoo 19 + Postgres setup for trying the modules in this
repo against a real running instance. Everything it creates lives inside
this `testing/` folder (gitignored) or in your own Odoo source checkout -
nothing here touches a system-wide Postgres or Homebrew service.

## First-time setup

Requires Homebrew's `postgresql@16` and a checkout of the Odoo 19 source
(this repo only holds our own modules, not Odoo core):

```
brew install postgresql@16
git clone --branch 19.0 --single-branch --depth 1 https://github.com/odoo/odoo.git ~/dev/odoo-19
```

Then, from this `testing/` directory:

```
./setup.sh
```

Creates `.venv/` (Odoo's Python dependencies) and `.pgdata/` (a fresh,
isolated Postgres cluster on port 5433). Safe to re-run.

If your Odoo checkout isn't at `~/dev/odoo-19`, set `ODOO_SRC` first:
`ODOO_SRC=/path/to/odoo-19 ./setup.sh`.

## Everyday use

```
./start.sh
```

Starts Postgres, then Odoo in the foreground at http://localhost:8069 -
**Ctrl+C stops both**, guaranteed, even if Odoo crashes (the script traps
EXIT/INT/TERM and won't return control to your prompt until both are
confirmed down). Don't leave it running unattended when you're not
actively testing.

`addons_path` automatically includes every folder at the root of this
repo, so a new module just needs to exist here - nothing to edit.

First run creates the `odoo_addons_test` database with no modules
installed yet. Install what you want to test:

```
source .venv/bin/activate
python3 ~/dev/odoo-19/odoo-bin --addons-path="$HOME/dev/odoo-19/addons,$HOME/dev/odoo-19/odoo/addons,$(cd .. && pwd)" \
    --db_host="$(pwd)/.sockets" --db_port=5433 -d odoo_addons_test \
    -i base,calendar,caldav_calendar --stop-after-init
```

(Swap `-i` for `-u` on later runs to upgrade an already-installed module
after editing its source.) Override `DB_NAME` or `HTTP_PORT` env vars if
you want a different database or port.

## Checking nothing's left running

```
ps aux | grep -E "odoo-bin|postgres" | grep -v grep
```

No output means fully stopped. If something's stuck: `./pg_stop.sh`, and
`pkill -f odoo-bin` for Odoo itself.

## Scripted testing without a browser

`odoo-bin shell` gives a Python shell with `env` bound to the database -
useful for exercising ORM logic directly (creating records, calling model
methods, checking results) without needing the web UI:

```
source .venv/bin/activate
python3 ~/dev/odoo-19/odoo-bin shell --addons-path="..." --db_host="$(pwd)/.sockets" --db_port=5433 \
    -d odoo_addons_test --shell-interface=python < your_script.py
```
