# -*- coding: utf-8 -*-


def migrate(cr, version):
    """signalwire.callback_request moves here from signalwire_voip_portal and
    gains a `source`. Every request that exists before this version came from
    the customer portal: set that before the new column's default
    ("receptionist") is filled in."""
    cr.execute("SELECT to_regclass('signalwire_callback_request')")
    if not cr.fetchone()[0]:
        return
    cr.execute("ALTER TABLE signalwire_callback_request ADD COLUMN IF NOT EXISTS source varchar")
    cr.execute("UPDATE signalwire_callback_request SET source = 'portal' WHERE source IS NULL")
