# -*- coding: utf-8 -*-
import hmac as py_hmac
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.misc import hmac

# No 0/O, 1/I/L: a key is read aloud over the phone.
KEY_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
KEY_MINUTES = 30
SMS_MINUTES = 10


class SupportVerificationCode(models.Model):
    """A one-time code a customer reads to the support team to prove who
    they are.

    Only a keyed hash of each code is stored, so nobody with database or
    screen access can look one up. A code works once, for one contact,
    until it expires.
    """
    _name = 'support.verification.code'
    _description = 'Support Verification Code'
    _order = 'id desc'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    kind = fields.Selection([
        ('support_key', 'Support key'),
        ('sms_code', 'Texted code'),
    ], required=True)
    code_hash = fields.Char(required=True)
    expires_at = fields.Datetime(required=True)
    used_at = fields.Datetime()

    @api.model
    def _hash(self, code):
        normalized = ''.join(ch for ch in (code or '').upper() if ch.isalnum())
        return hmac(self.env(su=True), 'support-verification-code', normalized)

    @api.model
    def _new_support_key(self):
        raw = ''.join(secrets.choice(KEY_ALPHABET) for _ in range(12))
        return '-'.join(raw[i:i + 4] for i in range(0, 12, 4))

    @api.model
    def _new_sms_code(self):
        return f'{secrets.randbelow(10 ** 6):06d}'

    @api.model
    def _issue(self, partner, kind):
        """Creates a code for this contact and returns it in clear, once.
        Earlier unused codes of the same kind stop working."""
        code = self._new_support_key() if kind == 'support_key' else self._new_sms_code()
        minutes = KEY_MINUTES if kind == 'support_key' else SMS_MINUTES
        now = fields.Datetime.now()
        self.sudo().search([
            ('partner_id', '=', partner.id), ('kind', '=', kind), ('used_at', '=', False),
        ]).write({'used_at': now})
        record = self.sudo().create({
            'partner_id': partner.id,
            'kind': kind,
            'code_hash': self._hash(code),
            'expires_at': now + timedelta(minutes=minutes),
        })
        return code, record.expires_at

    @api.model
    def _redeem(self, partner, code):
        """Uses up a valid code for this contact. Returns its kind, or False."""
        if not partner or not code:
            return False
        wanted = self._hash(code)
        candidates = self.sudo().search([
            ('partner_id', '=', partner.id),
            ('used_at', '=', False),
            ('expires_at', '>', fields.Datetime.now()),
        ])
        for candidate in candidates:
            if py_hmac.compare_digest(candidate.code_hash, wanted):
                candidate.used_at = fields.Datetime.now()
                return candidate.kind
        return False

    @api.model
    def _count_recent(self, partner, kind, hours=1):
        return self.sudo().search_count([
            ('partner_id', '=', partner.id), ('kind', '=', kind),
            ('create_date', '>', fields.Datetime.now() - timedelta(hours=hours)),
        ])

    @api.autovacuum
    def _gc_expired(self):
        self.sudo().search([
            ('expires_at', '<', fields.Datetime.now() - timedelta(days=7)),
        ]).unlink()
