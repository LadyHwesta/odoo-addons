# -*- coding: utf-8 -*-
from odoo import fields, models


class CalDAVPendingDelete(models.Model):
    """Tombstone queue: a calendar.event was deleted in Odoo before its
    matching CalDAV resource could be removed from the server. The push
    phase of the sync drains this queue and clears each row once the
    remote DELETE succeeds (or the resource is confirmed already gone).
    """
    _name = 'caldav.pending.delete'
    _description = 'CalDAV Pending Deletion'

    user_id = fields.Many2one('res.users', required=True, index=True, ondelete='cascade')
    href = fields.Char(required=True)
    etag = fields.Char()
