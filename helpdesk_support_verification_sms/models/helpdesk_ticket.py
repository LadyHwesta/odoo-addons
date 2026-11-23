# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError

MAX_TEXTS_PER_HOUR = 3


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def _verification_sms_number(self):
        self.ensure_one()
        if not self.company_id.support_sms_number_id and not self.env.company.support_sms_number_id:
            return ''
        partner = self.partner_id
        return (partner.support_mobile or partner.phone or '').strip()

    def _send_verification_sms(self):
        self.ensure_one()
        self._check_not_locked()
        sender = self.company_id.support_sms_number_id or self.env.company.support_sms_number_id
        number = self._verification_sms_number()
        if not sender or not number:
            return super()._send_verification_sms()
        codes = self.env['support.verification.code']
        if codes._count_recent(self.partner_id, 'sms_code') >= MAX_TEXTS_PER_HOUR:
            raise UserError(_("Three codes have already been texted to this customer in the "
                              "last hour. Use the last one, or ask for their support key."))
        code, _expires = codes._issue(self.partner_id, 'sms_code')
        company = self.company_id or self.env.company
        body = _("%(company)s support code: %(code)s. Read it to the person helping you. "
                 "It works once, for 10 minutes. We will never ask for your password.",
                 company=company.name, code=code)
        sender.sudo().send_sms(number, body, log_body=_(
            "%(company)s support code (hidden).", company=company.name))
        self.message_post(
            body=_("A verification code was texted to the number ending %(last)s.", last=number[-4:]),
            subtype_xmlid='mail.mt_note')
        return True
