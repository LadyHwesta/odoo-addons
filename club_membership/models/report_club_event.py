# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class ReportClubEvent(models.Model):
    _name = "report.club.event"
    _description = "Club Event Statistics"
    _auto = False
    _order = "date_begin desc"

    event_id = fields.Many2one("event.event", string="Event", readonly=True)
    date_begin = fields.Datetime(string="Start", readonly=True)
    event_type_id = fields.Many2one("event.type", string="Category", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)

    attendee_count = fields.Integer(string="Attendees", readonly=True)
    volunteer_confirmed = fields.Integer(string="Volunteers", readonly=True)
    volunteer_needed = fields.Integer(string="Volunteer Slots", readonly=True)
    volunteer_shortfall = fields.Integer(string="Unfilled Slots", readonly=True)
    roles_understaffed = fields.Integer(string="Understaffed Roles", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                SELECT
                    e.id AS id,
                    e.id AS event_id,
                    e.date_begin AS date_begin,
                    e.event_type_id AS event_type_id,
                    e.company_id AS company_id,
                    COALESCE(reg.cnt, 0) AS attendee_count,
                    COALESCE(v.confirmed, 0) AS volunteer_confirmed,
                    COALESCE(r.needed, 0) AS volunteer_needed,
                    GREATEST(COALESCE(r.needed, 0) - COALESCE(v.confirmed, 0), 0)
                        AS volunteer_shortfall,
                    COALESCE(r.understaffed, 0) AS roles_understaffed
                FROM event_event e
                LEFT JOIN (
                    SELECT event_id, COUNT(*) AS cnt
                    FROM event_registration
                    WHERE state IN ('open', 'done') AND active
                    GROUP BY event_id
                ) reg ON reg.event_id = e.id
                LEFT JOIN (
                    SELECT event_id,
                           COUNT(*) FILTER (WHERE state = 'confirmed') AS confirmed
                    FROM event_volunteer_assignment
                    GROUP BY event_id
                ) v ON v.event_id = e.id
                LEFT JOIN (
                    SELECT role.event_id,
                           SUM(role.slot_count) AS needed,
                           COUNT(*) FILTER (
                               WHERE role.slot_count > COALESCE(f.filled, 0)
                           ) AS understaffed
                    FROM event_volunteer_role role
                    LEFT JOIN (
                        SELECT role_id,
                               COUNT(*) FILTER (WHERE state IN ('draft', 'confirmed'))
                                   AS filled
                        FROM event_volunteer_assignment
                        GROUP BY role_id
                    ) f ON f.role_id = role.id
                    GROUP BY role.event_id
                ) r ON r.event_id = e.id
            )
        """)
