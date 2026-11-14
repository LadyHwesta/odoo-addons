# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MAX_FAILED = 5
LOCK_MINUTES = 15


class HelpdeskTicketStage(models.Model):
    _inherit = 'helpdesk.ticket.stage'

    requires_verification = fields.Boolean(
        string='Requires Verified Customer', default=True,
        help="A ticket can only move to this stage once the customer has been "
             "verified, or marked as needing no account access.")


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    verification_state = fields.Selection([
        ('unverified', 'Not verified'),
        ('verified', 'Verified'),
        ('not_needed', 'No account access needed'),
    ], string='Customer Verification', default='unverified', required=True,
        tracking=True, copy=False)
    verification_method = fields.Selection([
        ('portal', 'Signed in to the portal'),
        ('support_key', 'Support key'),
        ('sms_code', 'Texted code'),
        ('not_needed', 'Marked as not needed'),
        ('existing', 'Ticket from before verification'),
    ], string='Verified By Method', readonly=True, copy=False)
    verified_by_id = fields.Many2one('res.users', string='Verified By', readonly=True, copy=False)
    verified_on = fields.Datetime(readonly=True, copy=False)
    verification_failures = fields.Integer(readonly=True, copy=False)
    verification_locked_until = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        for vals in vals_list:
            # A customer who opens a ticket from the portal is signed in as
            # themselves: that is the strongest check there is.
            if (user.share and not user._is_public()
                    and vals.get('partner_id', user.partner_id.id) == user.partner_id.id):
                vals.update({
                    'partner_id': user.partner_id.id,
                    'verification_state': 'verified',
                    'verification_method': 'portal',
                    'verified_on': fields.Datetime.now(),
                })
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('stage_id'):
            stage = self.env['helpdesk.ticket.stage'].browse(vals['stage_id'])
            if stage.requires_verification:
                blocked = self.filtered(lambda t: t.verification_state == 'unverified')
                if blocked:
                    raise UserError(_(
                        "Verify the customer before moving %(tickets)s to %(stage)s. "
                        "Use Verify Customer on the ticket: ask for their support key, "
                        "or text them a code.",
                        tickets=', '.join(blocked.mapped('number')), stage=stage.name))
        if 'partner_id' in vals:
            # A different customer means a different person to verify.
            changed = self.filtered(lambda t: t.partner_id.id != vals['partner_id']
                                    and t.verification_method in ('support_key', 'sms_code', 'portal'))
            if changed:
                super(HelpdeskTicket, changed).write(self._unverified_values())
        return super().write(vals)

    @api.model
    def _unverified_values(self):
        return {'verification_state': 'unverified', 'verification_method': False,
                'verified_by_id': False, 'verified_on': False}

    def _check_not_locked(self):
        self.ensure_one()
        if self.verification_locked_until and self.verification_locked_until > fields.Datetime.now():
            raise UserError(_(
                "Too many wrong codes on this ticket. Try again after %(time)s, "
                "or ask a Helpdesk manager for help.",
                time=fields.Datetime.context_timestamp(self, self.verification_locked_until).strftime('%H:%M')))

    def _verify_with_code(self, code):
        """Checks a code the customer read out. Returns True when verified."""
        self.ensure_one()
        self._check_not_locked()
        if not self.partner_id:
            raise UserError(_("Set the ticket's contact first: a code belongs to one contact."))
        kind = self.env['support.verification.code']._redeem(self.partner_id, code)
        if not kind:
            failures = self.verification_failures + 1
            values = {'verification_failures': failures}
            if failures >= MAX_FAILED:
                values.update(verification_failures=0, verification_locked_until=
                              fields.Datetime.now() + timedelta(minutes=LOCK_MINUTES))
            self.sudo().write(values)
            self.message_post(body=_("A verification code didn't match (attempt %(n)s).", n=failures),
                              subtype_xmlid='mail.mt_note')
            return False
        self.sudo().write({
            'verification_state': 'verified', 'verification_method': kind,
            'verified_by_id': self.env.user.id, 'verified_on': fields.Datetime.now(),
            'verification_failures': 0, 'verification_locked_until': False,
        })
        label = dict(self._fields['verification_method'].selection)[kind]
        self.message_post(body=_("Customer verified with a %(method)s.", method=label.lower()),
                          subtype_xmlid='mail.mt_note')
        return True

    def action_mark_verification_not_needed(self):
        for ticket in self:
            ticket.write({
                'verification_state': 'not_needed', 'verification_method': 'not_needed',
                'verified_by_id': self.env.user.id, 'verified_on': fields.Datetime.now(),
            })
            ticket.message_post(
                body=_("Marked as needing no account access: no account details may be "
                       "discussed or changed on this ticket."),
                subtype_xmlid='mail.mt_note')

    def action_open_verify(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Verify Customer'),
            'res_model': 'helpdesk.ticket.verify',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_id': self.id},
        }

    # Texted codes: helpdesk_support_verification_sms fills these in.

    def _verification_sms_number(self):
        """The account holder's mobile number codes are texted to, if
        texting is set up."""
        return ''

    def _send_verification_sms(self):
        raise UserError(_("Texting isn't set up for support codes. Ask the customer for "
                          "their support key from the customer portal instead."))
