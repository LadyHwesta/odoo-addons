# -*- coding: utf-8 -*-
"""``activitypub.actor.display_name`` was a plain required Char, which
collides with Odoo's computed ``display_name`` magic field (the web client
would not let you edit it). It is now ``name``. Carry any existing rows
across before the ORM adds the ``NOT NULL`` on the new column.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'activitypub_actor'
           AND column_name IN ('display_name', 'name')
    """)
    columns = {row[0] for row in cr.fetchall()}
    if 'display_name' in columns and 'name' not in columns:
        cr.execute('ALTER TABLE activitypub_actor RENAME COLUMN display_name TO name')
