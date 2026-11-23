# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

ALERT_CHANNEL = 'signalwire_callback/alert'
CLOSED_CHANNEL = 'signalwire_callback/closed'


class SignalWireCallbackRequest(models.Model):
    """Someone asked to be called back: a caller on hold who pressed 1, a
    portal customer (signalwire_voip_portal), or a receptionist taking a
    message. Distinct from signalwire.live_call, a call in progress keyed
    by its call_sid: a request has no call in progress.

    Defined here (moved from signalwire_voip_portal in 19.0.4.16.0) so
    phone, portal and receptionist requests are one list. The person it's
    for is alerted when they're free, with Call now and Schedule.
    """
    _name = 'signalwire.callback_request'
    _description = 'Callback Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'phone_number'

    partner_id = fields.Many2one('res.partner', index=True, string="Contact")
    phone_number = fields.Char(required=True)
    note = fields.Text()
    source = fields.Selection(
        [('phone', "Caller on hold"), ('portal', "Customer portal"),
         ('receptionist', "Receptionist")],
        default='receptionist', required=True)
    state = fields.Selection(
        [('pending', "Pending"), ('claimed', "Claimed"), ('scheduled', "Scheduled"),
         ('completed', "Completed")],
        default='pending', required=True, tracking=True)
    claimed_by_user_id = fields.Many2one('res.users', tracking=True)
    target_user_id = fields.Many2one(
        'res.users', string="For", tracking=True,
        help="Who the caller was trying to reach. Alerted when they're free.")
    target_group_id = fields.Many2one(
        'signalwire.call.group', string="For Group",
        help="A call group the caller was trying to reach: whoever in it is "
             "free first is alerted.")
    live_call_id = fields.Many2one('signalwire.live_call', ondelete='set null')
    event_id = fields.Many2one('calendar.event', string="Scheduled Call", ondelete='set null')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)
    not_before = fields.Datetime(
        string="Call Back From", index=True,
        help="Not before this time: set for \"Callback when we open\" requests "
             "made after hours. Nobody is alerted until then.")
    alerted_at = fields.Datetime(copy=False)
    related_ref = fields.Reference(
        selection='_selection_related_models', string="About",
        help="What the call is about (a quote, ticket, task...). Opening the callback "
             "opens it; without it, the contact opens.")

    # Records a callback can be about, when their apps are installed.
    RELATED_MODELS = ['res.partner', 'sale.order', 'crm.lead', 'helpdesk.ticket', 'project.task',
                      'account.move', 'event.event', 'calendar.event']

    @api.model
    def _selection_related_models(self):
        return [(name, self.env[name]._description) for name in self.RELATED_MODELS if name in self.env]

    def _open_target(self):
        """What opening this callback should show: what it's about, else the
        contact, else the request itself. {'model', 'id'}"""
        self.ensure_one()
        related = self.related_ref
        if related and related.exists() and related.has_access('read'):
            return {'model': related._name, 'id': related.id}
        if self.partner_id:
            return {'model': 'res.partner', 'id': self.partner_id.id}
        return {'model': self._name, 'id': self.id}

    def action_open_target(self):
        target = self._open_target()
        return {'type': 'ir.actions.act_window', 'res_model': target['model'], 'res_id': target['id'],
                'views': [(False, 'form')], 'target': 'current'}

    def action_open_details(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'views': [(False, 'form')], 'target': 'current'}

    @api.model_create_multi
    def create(self, vals_list):
        requests = super().create(vals_list)
        requests._notify_panel()
        for request in requests:
            request.message_post(body=_(
                "Callback requested by %(who)s at %(number)s.",
                who=request._caller_name(), number=request.phone_number))
        requests._alert_free_users()
        return requests

    def _caller_name(self):
        self.ensure_one()
        return self.partner_id.name or self.phone_number

    def _target_label(self):
        self.ensure_one()
        return self.target_user_id.name or self.target_group_id.name or ''

    def _notify_panel(self):
        """Every open receptionist panel reloads (same channel as live calls)."""
        group = self.env.ref('signalwire_voip_click2call.group_signalwire_receptionist')
        self.env['bus.bus']._sendone(group, 'signalwire_live_call/updated', {})

    def _users_to_alert(self):
        self.ensure_one()
        if self.state != 'pending' or (
                self.not_before and self.not_before > fields.Datetime.now()):
            return self.env['res.users']
        users = self.target_user_id | self.target_group_id.member_ids
        return users.filtered(lambda u: u.voip_username and u._signalwire_is_free())

    def _alert_payload(self):
        self.ensure_one()
        return {
            'id': self.id,
            'caller': self._caller_name(),
            'phone_number': self.phone_number,
            'partner_id': self.partner_id.id,
            'note': self.note or '',
            'for': self._target_label(),
            'requested': fields.Datetime.to_string(self.create_date),
        }

    def _alert_free_users(self, users=None):
        """Pops a "Call now / Schedule" alert for each person it's for who
        is free right now (or just `users`). The browser ignores repeats of
        an alert that's already showing."""
        Bus = self.env['bus.bus'].sudo()
        for request in self.sudo().sorted('create_date'):
            alerted = False
            for user in request._users_to_alert():
                if users is None or user in users:
                    Bus._sendone(user.partner_id, ALERT_CHANNEL, request._alert_payload())
                    alerted = True
            if alerted and not request.alerted_at:
                request.alerted_at = fields.Datetime.now()

    @api.model
    def _cron_alert_due_callbacks(self):
        """"Callback when we open" requests: once their time has come,
        alert whoever is free in the group, in the order people called."""
        self.sudo().search([
            ('state', '=', 'pending'), ('alerted_at', '=', False),
            ('not_before', '!=', False), ('not_before', '<=', fields.Datetime.now()),
        ], order='create_date')._alert_free_users()

    def _close_alerts(self):
        """Someone dealt with it: close everyone else's alert."""
        Bus = self.env['bus.bus'].sudo()
        for request in self.sudo():
            for user in request.target_user_id | request.target_group_id.member_ids:
                Bus._sendone(user.partner_id, CLOSED_CHANNEL, {'id': request.id})

    def _check_open(self):
        for request in self:
            if request.state in ('scheduled', 'completed'):
                raise UserError(_(
                    "%(who)s's callback was already handled by %(user)s.",
                    who=request._caller_name(),
                    user=request.claimed_by_user_id.name or _("someone else")))
            if request.state == 'claimed' and request.claimed_by_user_id != self.env.user:
                raise UserError(_(
                    "%(user)s is already calling %(who)s back.",
                    user=request.claimed_by_user_id.name, who=request._caller_name()))

    def action_claim(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("This request has already been claimed."))
        self.write({'state': 'claimed', 'claimed_by_user_id': self.env.uid})
        self.activity_schedule(
            'mail.mail_activity_data_todo', user_id=self.env.uid,
            summary=_("Call back %(who)s", who=self._caller_name()),
            note=_("Requested number: %(number)s", number=self.phone_number))
        self._close_alerts()
        self._notify_panel()

    def action_call_now(self):
        """The person is calling back now from their softphone; returns the
        number for the browser to dial. Counts as done."""
        self.ensure_one()
        self._check_open()
        self.write({'state': 'completed', 'claimed_by_user_id': self.env.uid})
        self.activity_ids.action_done()
        self.message_post(body=_("Called back by %(user)s.", user=self.env.user.name))
        self._close_alerts()
        self._notify_panel()
        return self.phone_number

    def action_complete(self):
        self.ensure_one()
        self.state = 'completed'
        self.activity_ids.filtered(lambda a: a.user_id == self.env.user).action_done()
        self._close_alerts()
        self._notify_panel()

    @api.model
    def schedule_signalwire_callback(self, values):
        """Books a callback in the calendar, from the receptionist panel or
        a callback alert. `values`: user_id, start (UTC "YYYY-MM-DD
        HH:MM:SS"), duration (minutes), note, and either request_id or a
        new request's phone_number / partner_id. email_caller sends the
        caller a calendar invitation (off by default). api.model: called
        over RPC with one dict. Returns the event id."""
        user = self.env['res.users'].browse(int(values['user_id'])).exists()
        if not user:
            raise UserError(_("Pick who should make the call."))
        start = fields.Datetime.to_datetime(values['start'])
        if not start:
            raise UserError(_("Pick when the call should happen."))
        duration = int(values.get('duration') or 15)
        if values.get('request_id'):
            request = self.browse(int(values['request_id'])).exists()
            if not request:
                raise UserError(_("This callback request no longer exists."))
            request._check_open()
        else:
            if not (values.get('phone_number') or values.get('partner_id')):
                raise UserError(_("Enter the number to call back."))
            partner = self.env['res.partner'].browse(int(values.get('partner_id') or 0)).exists()
            request = self.create({
                'source': 'receptionist',
                'phone_number': values.get('phone_number') or partner.phone or '',
                'partner_id': partner.id or False,
                'target_user_id': user.id,
                'note': values.get('note') or False,
                'state': 'claimed',
                'claimed_by_user_id': user.id,
            })
        note = values.get('note') or request.note or ''
        attendees = user.partner_id | request.partner_id
        Event = self.env['calendar.event'].with_context(no_mail_to_attendees=True)
        event = Event.create({
            'name': _("Callback: %(who)s", who=request._caller_name()),
            'start': start,
            'stop': start + timedelta(minutes=duration),
            'user_id': user.id,
            'partner_ids': [(6, 0, attendees.ids)],
            'description': _("Call %(number)s. %(note)s",
                             number=request.phone_number, note=note).strip(),
        })
        if values.get('email_caller') and request.partner_id.email:
            event.attendee_ids.filtered(
                lambda a: a.partner_id == request.partner_id)._send_invitation_emails()
        request.write({
            'state': 'scheduled', 'event_id': event.id, 'claimed_by_user_id': user.id,
            'target_user_id': request.target_user_id.id or user.id,
        })
        request.message_post(body=_(
            "Callback scheduled with %(user)s.", user=user.name))
        request._close_alerts()
        request._notify_panel()
        return event.id
