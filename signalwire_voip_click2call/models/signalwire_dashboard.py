# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import AccessError

LIVE_STATES = ('ringing', 'parked', 'connected')


class SignalWireDashboard(models.AbstractModel):
    _inherit = 'signalwire.dashboard'

    def _can_switch_open_closed(self):
        user = self.env.user
        return user.has_group('signalwire_voip_click2call.group_signalwire_receptionist') \
            or user.has_group('base.group_system')

    @api.model
    def set_phones_closed(self, closed):
        """The dashboard's Close for the Rest of Today / Reopen Now button,
        with the same rule as the Open / Closed screen."""
        if not self._can_switch_open_closed():
            raise AccessError(_("Only receptionists and administrators can open or close the phones."))
        company = self.env.company.sudo()
        if closed:
            company.with_context(tz=self.env.user.tz).action_signalwire_close_today()
        else:
            company.action_signalwire_reopen()
        return True

    def _dashboard_parts(self, data):
        super()._dashboard_parts(data)
        Number = self.env['signalwire.phone_number']
        until = self.env.company._signalwire_closed_until()
        with_hours = Number.search_count([('calendar_id', '!=', False)])
        data['status'] = {
            'closed': bool(until),
            'title': _("Closed early") if until else _("Open as usual"),
            'text': (_("Calls use each number's outside-business-hours routing until %(until)s.",
                       until=Number._format_local(until)) if until else
                     _("Calls follow each number's Business Hours (%(count)s numbers have them set).",
                       count=with_hours)),
            'can_toggle': self._can_switch_open_closed(),
        }

        Voicemail = self.env['signalwire.voicemail']
        unheard = Voicemail.search_count([('is_read', '=', False)])
        data['tiles'].append({
            'key': 'voicemail', 'sequence': 10,
            'label': _("Unheard voicemail"), 'value': unheard,
            'hint': _("Yours and your groups'"),
            'tone': 'warning' if unheard else 'ok',
            'action': self._list_action(_("Unheard Voicemail"), Voicemail._name,
                                        [('is_read', '=', False)]),
        })

        LiveCall = self.env['signalwire.live_call']
        if LiveCall.has_access('read'):
            live = LiveCall.search_count([('state', 'in', LIVE_STATES)])
            data['tiles'].append({
                'key': 'live_calls', 'sequence': 50,
                'label': _("Calls in progress"), 'value': live,
                'hint': _("Ringing, on hold or connected"),
                'tone': 'info' if live else 'muted',
                'action': self.env['ir.actions.actions']._for_xml_id(
                    'signalwire_voip_click2call.action_signalwire_receptionist_panel'),
            })

        call_states = {'idle': _("Available"), 'ringing': _("Ringing"), 'on_call': _("On a call")}
        users = self.env['res.users'].search(
            [('share', '=', False), ('signalwire_sip_endpoint_id', '!=', False)], order='name')
        extension_form = self.env.ref('signalwire_voip_click2call.view_users_signalwire_extension_form')
        data['tables'].append({
            'key': 'extensions',
            'title': _("Extensions"),
            'sequence': 20,
            'columns': [_("Person"), _("Now"), _("If they don't answer")],
            'rows': [{
                'cells': [
                    user.name,
                    call_states.get(user.signalwire_call_state, ""),
                    (_("Forwards to %(name)s", name=user.signalwire_active_forward_id.name)
                     if user.signalwire_active_forward_id else
                     _("Voicemail") if user.signalwire_voicemail_enabled else _("Keeps ringing")),
                ],
                'tone': 'ok' if user.signalwire_call_state == 'idle' else 'warning',
                'open': {'res_model': 'res.users', 'res_id': user.id, 'view_id': extension_form.id},
            } for user in users],
            'empty': _("Nobody has a softphone yet. Set one up from Extensions."),
        })

    def _number_route_now(self, number):
        route_type, target = number._effective_route()
        if not target:
            return _("Not set up yet: open it to choose where calls go")
        phrase = number._route_phrase(route_type, target)
        if not number.calendar_id:
            return phrase[0].upper() + phrase[1:]
        if number.company_closed_early:
            return _("Closed early: %(phrase)s", phrase=phrase)
        if number._is_within_business_hours():
            return _("Open: %(phrase)s", phrase=phrase)
        return _("After hours: %(phrase)s", phrase=phrase)

    def _number_tone(self, number):
        route_type, target = number._effective_route()
        if not number.inbound_connected or not target:
            return 'warning'
        return 'ok'
