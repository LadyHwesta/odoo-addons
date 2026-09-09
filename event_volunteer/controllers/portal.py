# -*- coding: utf-8 -*-
from urllib.parse import urlencode

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request


class EventVolunteerPortal(http.Controller):

    def _back_to_event(self, event, message=None, ok=True):
        url = event.website_url or ("/event/%s" % event.id)
        params = {}
        if message:
            params = {"volunteer_msg": message, "volunteer_ok": "1" if ok else "0"}
        if params:
            url = "%s?%s" % (url, urlencode(params))
        return request.redirect("%s#event_volunteer_roles" % url)

    @http.route(
        ["/event/<int:event_id>/volunteer/<int:role_id>"],
        type="http", auth="user", website=True, methods=["POST"])
    def event_volunteer_signup(self, event_id, role_id, **post):
        role = request.env["event.volunteer.role"].sudo().browse(role_id).exists()
        if not role or role.event_id.id != event_id:
            return request.not_found()
        partner = request.env.user.partner_id
        try:
            role.action_portal_volunteer(partner)
        except UserError as exc:
            return self._back_to_event(role.event_id, exc.args[0], ok=False)
        return self._back_to_event(
            role.event_id,
            request.env._("You're signed up as %s. Thanks!", role.name))

    @http.route(
        ["/event/volunteer/<int:assignment_id>/withdraw"],
        type="http", auth="user", website=True, methods=["POST"])
    def event_volunteer_withdraw(self, assignment_id, **post):
        assignment = request.env["event.volunteer.assignment"].sudo().browse(
            assignment_id).exists()
        if not assignment:
            return request.not_found()
        partner = request.env.user.partner_id
        if assignment.partner_id != partner:
            return request.not_found()
        event = assignment.event_id
        assignment.action_portal_withdraw()
        return self._back_to_event(
            event, request.env._("You've withdrawn from %s.", assignment.role_id.name))
