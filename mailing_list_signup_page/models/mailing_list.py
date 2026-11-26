# -*- coding: utf-8 -*-
import re
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import ValidationError

SLUG = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


class MailingList(models.Model):
    _inherit = 'mailing.list'

    signup_page_slug = fields.Char(
        'Signup Page Address', copy=False,
        help="The last part of the signup page's address: 'news' gives /join/news. "
             "Lowercase letters, digits and hyphens. Only public lists can have one.")
    # A plain string, never _(): translating in a field default breaks module loading.
    signup_page_title = fields.Char('Signup Page Title', translate=True, default='Nice to meet you!')
    signup_page_intro = fields.Text(
        'Signup Page Introduction', translate=True,
        help="A sentence or two under the title: what people will get, and how often.")
    signup_page_url = fields.Char('Signup Page', compute='_compute_signup_page_urls')
    signup_page_qr_path = fields.Char(compute='_compute_signup_page_urls')
    signup_page_qr_url = fields.Char('QR Code', compute='_compute_signup_page_urls')

    _signup_page_slug_unique = models.Constraint(
        'UNIQUE(signup_page_slug)',
        'Another mailing list already uses this signup page address.',
    )

    @api.depends('signup_page_slug')
    def _compute_signup_page_urls(self):
        for mailing_list in self:
            if not mailing_list.signup_page_slug:
                mailing_list.signup_page_url = False
                mailing_list.signup_page_qr_path = False
                mailing_list.signup_page_qr_url = False
                continue
            base = mailing_list.get_base_url()
            url = f'{base}/join/{mailing_list.signup_page_slug}'
            # Error correction M: still scans when printed small or a bit smudged.
            path = (f'/report/barcode/?barcode_type=QR&value={quote(url, safe="")}'
                    f'&width=600&height=600&barLevel=M')
            mailing_list.signup_page_url = url
            mailing_list.signup_page_qr_path = path
            mailing_list.signup_page_qr_url = base + path

    @api.constrains('signup_page_slug', 'is_public')
    def _check_signup_page_slug(self):
        for mailing_list in self.filtered('signup_page_slug'):
            if not SLUG.match(mailing_list.signup_page_slug):
                raise ValidationError(self.env._(
                    "The signup page address can only use lowercase letters, digits and "
                    "hyphens, like 'news' or 'spring-fair'."))
            if not mailing_list.is_public:
                raise ValidationError(self.env._(
                    "Only a public mailing list can have a signup page. Tick 'Show In "
                    "Preferences' (public) first."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._clean_signup_page_slug(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._clean_signup_page_slug(vals)
        return super().write(vals)

    @staticmethod
    def _clean_signup_page_slug(vals):
        if vals.get('signup_page_slug'):
            vals['signup_page_slug'] = vals['signup_page_slug'].strip().lower()
