# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.web.controllers.webmanifest import WebManifest
from odoo.http import request

# The sizes /web/manifest.webmanifest actually asks for, mapped to Odoo's
# own stock artwork - what we fall back to when no custom icon has been
# configured. Anything else requested (namely the 180x180 apple-touch-icon)
# falls back to the iOS-specific default instead.
_FALLBACK_ICONS = {
    (192, 192): '/web/static/img/odoo-icon-192x192.png',
    (512, 512): '/web/static/img/odoo-icon-512x512.png',
}
_FALLBACK_ICON_DEFAULT = '/web/static/img/odoo-icon-ios.png'


class WebPwaIconWebManifest(WebManifest):

    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        if request.env.company.pwa_icon:
            manifest['icons'] = [{
                'src': '/web/pwa_icon/%dx%d' % size,
                'sizes': '%dx%d' % size,
                'type': 'image/png',
            } for size in _FALLBACK_ICONS]
        return manifest

    @http.route('/web/pwa_icon/<int:width>x<int:height>', type='http',
                auth='public', readonly=True)
    def pwa_icon(self, width, height):
        """Serve the current company's custom PWA icon, resized to the
        requested dimensions, or fall back to Odoo's own artwork if no
        custom icon has been configured."""
        company = request.env.company
        if not company.pwa_icon:
            fallback = _FALLBACK_ICONS.get((width, height), _FALLBACK_ICON_DEFAULT)
            return request.redirect(fallback)
        stream = request.env['ir.binary']._get_image_stream_from(
            company, 'pwa_icon', width=width, height=height,
        )
        return stream.get_response()
