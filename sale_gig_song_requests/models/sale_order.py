# -*- coding: utf-8 -*-
import base64
import secrets
from io import BytesIO

import qrcode

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    song_request_token = fields.Char(copy=False, index=True, groups='sales_team.group_sale_salesman',
                                     default=lambda self: secrets.token_urlsafe(12))
    song_requests_enabled = fields.Boolean(
        string="Take Song Requests", default=True,
        help="Guests can request songs from the link or QR card until the gig ends.")
    song_request_url = fields.Char(compute='_compute_song_request_url', string="Song Request Link")
    song_request_ids = fields.One2many('gig.song.request', 'order_id', string="All Songs")
    song_guest_ids = fields.One2many('gig.song.request', 'order_id', string="Guest Requests",
                                     domain=[('kind', '=', 'request')])
    song_must_ids = fields.One2many('gig.song.request', 'order_id', string="Must Play",
                                    domain=[('kind', '=', 'must_play')])
    song_never_ids = fields.One2many('gig.song.request', 'order_id', string="Do Not Play",
                                     domain=[('kind', '=', 'do_not_play')])
    song_request_count = fields.Integer(compute='_compute_song_counts')

    @api.depends('song_request_ids.kind')
    def _compute_song_counts(self):
        for order in self:
            order.song_request_count = len(order.song_request_ids.filtered(lambda r: r.kind == 'request'))

    def _song_base_url(self):
        """The gig's own brand's address: the order's website, else the first
        website of the order's company that has a domain, else this server's."""
        self.ensure_one()
        website = self.website_id if 'website_id' in self._fields else self.env['website']
        if not website or not website.domain:
            website = self.env['website'].sudo().search(
                [('company_id', '=', self.company_id.id), ('domain', '!=', False)], limit=1)
        if website.domain:
            domain = website.domain
            return domain if '://' in domain else f'https://{domain}'
        return self.get_base_url()

    @api.depends('song_request_token', 'company_id')
    def _compute_song_request_url(self):
        for order in self:
            token = order.sudo().song_request_token
            order.song_request_url = f"{order._song_base_url().rstrip('/')}/gig/{token}/songs" if token else False

    def _song_request_qr_src(self):
        """The QR code as a PNG data URL, drawn with the qrcode library (and
        Pillow) Odoo already requires: it prints even where reportlab can't
        make images (pip installs without its PNG renderer)."""
        self.ensure_one()
        if not self.song_request_url:
            return ''
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        qr.add_data(self.song_request_url)
        qr.make(fit=True)
        stream = BytesIO()
        qr.make_image(fill_color='black', back_color='white').save(stream, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()

    def _song_requests_open(self):
        """Guests can request from booking until the gig ends."""
        self.ensure_one()
        return bool(self.song_requests_enabled and self.state == 'sale' and self.gig_end
                    and fields.Datetime.now() <= self.gig_end)

    def _song_lists_open(self):
        """The client can change their lists until the gig starts."""
        return self._gig_client_edit_open()

    def action_print_song_card(self):
        return self.env.ref('sale_gig_song_requests.action_report_song_card').report_action(self)
