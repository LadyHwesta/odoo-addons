# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


class TelehealthSignalWireController(http.Controller):

    @http.route(
        '/telehealth/signalwire/join/<string:access_token>',
        type='http', auth='public', website=True, sitemap=False)
    def join(self, access_token, **kwargs):
        """A stable, Odoo-hosted URL (same shape as Discuss's own
        calendar/join_videocall/<token> route) - a fresh room token is
        generated on every visit rather than baked in ahead of time,
        since a room token is a JWT that could otherwise expire before
        a real appointment, booked days out, actually happens.
        """
        event = request.env['calendar.event'].sudo().search(
            [('access_token', '=', access_token)], limit=1)
        if not event or not event.signalwire_room_name:
            raise NotFound()

        server = event.user_id.signalwire_video_subproject_id.server_id
        if not server:
            raise NotFound()

        participant_name = kwargs.get('name') or (
            request.env.user.name if not request.env.user._is_public()
            else 'Guest')
        result = server._get_client().video_post(
            'room_tokens', room_name=event.signalwire_room_name,
            user_name=participant_name)

        return request.render('telehealth_booking_signalwire.join_page', {
            'event': event,
            'room_token': result['token'],
        })
