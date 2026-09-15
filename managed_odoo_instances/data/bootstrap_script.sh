#!/usr/bin/env bash
# Bootstraps a bare Debian/Ubuntu server into an Odoo host: Postgres,
# Odoo itself, nginx + certbot, and this repo's own deploy agent as a
# systemd service. Meant to be run ONCE, by hand, over SSH, by Tiesa -
# never sent to a customer (see managed_odoo_instances' own README for
# why: it's delivered as an attachment on a generated project task,
# not emailed out).
#
# NOT YET LIVE-VERIFIED against a real box - built from Odoo's own
# documented official install method and standard Debian/nginx/certbot
# practice, but this whole script needs a real run against a
# disposable VPS before it's trusted with an actual paying customer's
# deployment (see this repo's README, "Verification").
#
# ONE THING THIS SCRIPT DELIBERATELY DOES NOT DO: install the
# X-Odoo-Dbfilter-reading middleware that routes each vhost to its own
# database (see the odoo_proxy.conf snippet's own header comment) -
# that already exists on the user's own shared server, but how it's
# packaged/installed isn't something this project has visibility into.
# A DEDICATED-server deployment needs that middleware installed by
# hand too, as a real manual step - flagged again at the end of this
# script's own output, not silently skipped.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run this as root (sudo bash bootstrap.sh)." >&2
    exit 1
fi

AGENT_REPO="${AGENT_REPO:-https://github.com/LadyHwesta/meskis-deploy-agent.git}"
AGENT_DIR="/opt/meskis-deploy-agent"
AGENT_USER="meskis-deploy-agent"
AGENT_ENV_DIR="/etc/meskis-deploy-agent"
AGENT_PORT="8765"

echo "== Installing prerequisites =="
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx postgresql \
    python3-venv python3-pip git wget gnupg sudo

echo "== Installing Odoo 19 from the official apt repository =="
wget -q -O /usr/share/keyrings/odoo-archive-keyring.gpg https://nightly.odoo.com/odoo.key
echo "deb [signed-by=/usr/share/keyrings/odoo-archive-keyring.gpg] https://nightly.odoo.com/19.0/nightly/deb/ ./" \
    > /etc/apt/sources.list.d/odoo.list
apt-get update
apt-get install -y odoo

echo "== Configuring Postgres for Odoo =="
ODOO_DB_PASSWORD="$(openssl rand -hex 24)"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='odoo'" | grep -q 1 || \
    sudo -u postgres createuser --createdb --no-superuser --no-createrole odoo
sudo -u postgres psql -c "ALTER USER odoo WITH PASSWORD '${ODOO_DB_PASSWORD}';"

echo "== Writing /etc/odoo/odoo.conf =="
mkdir -p /etc/odoo
ADMIN_MASTER_PASSWORD="$(openssl rand -hex 24)"
cat > /etc/odoo/odoo.conf <<EOF
[options]
admin_passwd = ${ADMIN_MASTER_PASSWORD}
db_host = 127.0.0.1
db_port = 5432
db_user = odoo
db_password = ${ODOO_DB_PASSWORD}
list_db = False
proxy_mode = True
EOF
chown odoo:odoo /etc/odoo/odoo.conf
chmod 640 /etc/odoo/odoo.conf

echo "== nginx: shared upstreams + the odoo_proxy.conf snippet =="
mkdir -p /etc/nginx/snippets
cp "$(dirname "$0")/../templates/odoo_proxy.conf" /etc/nginx/snippets/odoo_proxy.conf
cat > /etc/nginx/conf.d/odoo-upstreams.conf <<'EOF'
upstream odoo {
    server 127.0.0.1:8069;
}
upstream odoochat {
    server 127.0.0.1:8072;
}
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
EOF
nginx -t
systemctl reload nginx

echo "== Creating the ${AGENT_USER} system user =="
id -u "${AGENT_USER}" &>/dev/null || useradd --system --home "${AGENT_DIR}" --shell /usr/sbin/nologin "${AGENT_USER}"

# Narrow, explicit filesystem grants - not broad /etc access.
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled /var/log/meskis-deploy-agent
chgrp "${AGENT_USER}" /etc/nginx/sites-available /etc/nginx/sites-enabled
chmod g+w /etc/nginx/sites-available /etc/nginx/sites-enabled
chown "${AGENT_USER}:${AGENT_USER}" /var/log/meskis-deploy-agent

echo "== Narrow sudoers grant (nginx reload + certbot only) =="
install -m 0440 "$(dirname "$0")/../deploy/sudoers.d/meskis-deploy-agent" \
    /etc/sudoers.d/meskis-deploy-agent
visudo -c

echo "== Cloning and installing the agent itself =="
if [[ ! -d "${AGENT_DIR}" ]]; then
    git clone "${AGENT_REPO}" "${AGENT_DIR}"
fi
python3 -m venv "${AGENT_DIR}/.venv"
"${AGENT_DIR}/.venv/bin/pip" install --upgrade pip
"${AGENT_DIR}/.venv/bin/pip" install -r "${AGENT_DIR}/requirements.txt"
chown -R "${AGENT_USER}:${AGENT_USER}" "${AGENT_DIR}"

echo "== Generating this server's own agent bearer token =="
AGENT_TOKEN="$(openssl rand -hex 32)"
mkdir -p "${AGENT_ENV_DIR}"
cat > "${AGENT_ENV_DIR}/agent.env" <<EOF
AGENT_TOKEN=${AGENT_TOKEN}
ODOO_BIN=/usr/bin/odoo
ODOO_CONF=/etc/odoo/odoo.conf
NGINX_SITES_AVAILABLE=/etc/nginx/sites-available
NGINX_SITES_ENABLED=/etc/nginx/sites-enabled
NGINX_SNIPPET_PATH=/etc/nginx/snippets/odoo_proxy.conf
CERTBOT_EMAIL=admin@meskis.net
AGENT_LOG_PATH=/var/log/meskis-deploy-agent/agent.log
EOF
chown "${AGENT_USER}:${AGENT_USER}" "${AGENT_ENV_DIR}/agent.env"
chmod 640 "${AGENT_ENV_DIR}/agent.env"

install -m 0644 "${AGENT_DIR}/deploy/meskis-deploy-agent.service" \
    /etc/systemd/system/meskis-deploy-agent.service
systemctl daemon-reload
systemctl enable --now meskis-deploy-agent
systemctl enable --now postgresql odoo nginx

echo ""
echo "================================================================"
echo "Bootstrap complete."
echo ""
echo "Agent bearer token (paste into this server's deployment.server"
echo "record in Odoo, field agent_token - shown once, not saved"
echo "anywhere else):"
echo ""
echo "    ${AGENT_TOKEN}"
echo ""
echo "Odoo master (admin_passwd) password, for this server's own"
echo "database-manager screen if you ever need it by hand:"
echo ""
echo "    ${ADMIN_MASTER_PASSWORD}"
echo ""
echo "STILL NEEDS DOING BY HAND, NOT AUTOMATED BY THIS SCRIPT:"
echo "  - Install the X-Odoo-Dbfilter middleware (see this script's"
echo "    own header comment) - the agent's vhosts will set the"
echo "    header correctly, but nothing routes on it yet without this."
echo "================================================================"
