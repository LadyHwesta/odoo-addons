# -*- coding: utf-8 -*-
"""19.0.1.x -> 19.0.2.0.0: one CalDAV account per user becomes many.

The old flat caldav_* fields on res.users become a new caldav.account
model (one2many from res.users), and calendar.event's caldav_sync_user_id
(Many2one res.users) becomes caldav_account_id (Many2one caldav.account).

Runs *after* the new schema is in place, so the new caldav_account table
and calendar_event.caldav_account_id column already exist; the old
columns being migrated away from still exist too (Odoo doesn't drop
columns for removed fields on its own), so it's read here via raw SQL
since the ORM no longer declares them.
"""
from odoo import SUPERUSER_ID, api


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _column_exists(cr, 'res_users', 'caldav_url'):
        return  # nothing from the old schema to migrate

    cr.execute("""
        SELECT id, caldav_discovery_url, caldav_url, caldav_username, caldav_password,
               caldav_sync_status, caldav_sync_token, caldav_sync_ctag,
               caldav_last_sync, caldav_last_sync_error
        FROM res_users
        WHERE caldav_url IS NOT NULL
    """)
    old_configs = cr.fetchall()
    if not old_configs:
        return

    events_have_old_column = _column_exists(cr, 'calendar_event', 'caldav_sync_user_id')

    env = api.Environment(cr, SUPERUSER_ID, {})
    Account = env['caldav.account']
    for (user_id, discovery_url, url, username, password,
         sync_status, sync_token, sync_ctag, last_sync, last_sync_error) in old_configs:
        account = Account.create({
            'user_id': user_id,
            'name': 'Calendar',
            'discovery_url': discovery_url,
            'url': url,
            'username': username,
            'password': password,
            'sync_status': sync_status or 'not_configured',
            'sync_token': sync_token,
            'sync_ctag': sync_ctag,
            'last_sync': last_sync,
            'last_sync_error': last_sync_error,
        })
        if events_have_old_column:
            cr.execute(
                "UPDATE calendar_event SET caldav_account_id = %s WHERE caldav_sync_user_id = %s",
                (account.id, user_id),
            )
