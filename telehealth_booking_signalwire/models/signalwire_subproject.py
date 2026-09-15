# -*- coding: utf-8 -*-
from odoo import models


class SignalWireSubproject(models.Model):
    _inherit = 'signalwire.subproject'

    def _sync_video_cdrs(self, contract_line, date_from, date_to):
        """Video's own equivalent of signalwire_voip_sale's own
        _sync_cdrs, producing the exact same signalwire.cdr shape so
        nothing about billing or the PDF statement needs to know which
        one a given line uses - but the underlying API is a genuinely
        different, two-level shape: list this subproject's room
        sessions for the period, then list each session's own members
        for the actual per-participant duration/cost (confirmed live
        2026-09-15 that /api/video/rooms, /api/video/room_tokens, and
        /api/video/room_sessions all exist and work; the member-level
        fields and the room_sessions date-filter param names below are
        NOT independently verified - no real session exists yet to
        check them against, since creating one needs an actual joined
        WebRTC call. Sourced from SignalWire's own docs/search results
        rather than guessed blind - confirm the moment a real premium
        telehealth call has actually happened).

        Does not paginate, same accepted limitation as _sync_cdrs.
        """
        self.ensure_one()
        client = self.server_id._get_client()
        markup = 1 + (self.server_id.markup_percentage or 0.0) / 100.0
        existing_sids = set(self.env['signalwire.cdr'].search(
            [('subproject_id', '=', self.id)]).mapped('sid'))

        sessions = client.video_get('room_sessions', **{
            'started_at>': date_from.isoformat(),
            'started_at<': date_to.isoformat(),
        })
        for session in sessions.get('data', []):
            members = client.video_get(f"room_sessions/{session['id']}/members")
            for member in members.get('data', []):
                sid = member.get('id')
                if not sid or sid in existing_sids:
                    continue
                wholesale = abs(float(member.get('cost_in_dollars') or 0.0))
                billed = wholesale * markup
                duration = int(member.get('duration') or 0)
                minutes = duration / 60.0
                rate = (billed / minutes) if minutes else billed
                self.env['signalwire.cdr'].create({
                    'subproject_id': self.id,
                    'sid': sid,
                    'record_type': 'video',
                    'date': member.get('join_time'),
                    'from_number': member.get('name'),
                    'to_number': session.get('name'),
                    'duration': duration,
                    'wholesale_cost': wholesale,
                    'rate': rate,
                    'billed_amount': billed,
                    'contract_line_id': contract_line.id,
                })
                existing_sids.add(sid)

        return self.env['signalwire.cdr'].search([
            ('contract_line_id', '=', contract_line.id),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ])
