# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

# web_pwa_customize stores each resized variant as an ir.attachment whose
# `url` looks like /web_pwa_customize/icon<W>x<H>.<ext> (or, for an SVG
# upload, just /web_pwa_customize/icon.svg with no size suffix at all).
# Apple has no single canonical size; 192x192 is the closest of the ones
# web_pwa_customize actually generates to the commonly-recommended 180x180,
# so it's tried first, then whatever else exists, then Odoo's own default.
_ICON_URL_BASE = '/web_pwa_customize/icon'
_PREFERRED_SIZES = ['192x192', '256x256', '152x152', '144x144', '128x128', '512x512']
_FALLBACK_ICON = '/web/static/img/odoo-icon-ios.png'


class WebPwaIconAppleTouchIcon(http.Controller):

    def _custom_apple_touch_icon_url(self):
        """The best available web_pwa_customize icon URL for iOS, or None
        if no custom icon has been configured at all."""
        attachments = request.env['ir.attachment'].sudo().search([
            ('url', 'like', _ICON_URL_BASE),
        ])
        by_url = {a.url: a for a in attachments}
        for size in _PREFERRED_SIZES:
            url = f'{_ICON_URL_BASE}{size}.png'
            if url in by_url:
                return url
        # No sized PNG variants - either nothing configured, or an SVG
        # upload (web_pwa_customize doesn't resize those, it only ever
        # writes the one un-suffixed attachment).
        svg = by_url.get(f'{_ICON_URL_BASE}.svg')
        return svg.url if svg else None

    @http.route('/web/pwa_icon/apple-touch-icon.png', type='http',
                auth='public', readonly=True)
    def apple_touch_icon(self):
        url = self._custom_apple_touch_icon_url()
        return request.redirect(url or _FALLBACK_ICON)
