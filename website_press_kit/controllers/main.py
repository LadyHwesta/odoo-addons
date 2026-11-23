# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PressKit(http.Controller):

    def _kit(self):
        return request.env['website.press.kit'].sudo().search(
            [('website_id', '=', request.website.id), ('is_published', '=', True)], limit=1)

    @http.route('/press-kit', type='http', auth='public', website=True, sitemap=True)
    def press_kit(self, **kwargs):
        kit = self._kit()
        if not kit:
            raise request.not_found()
        return request.render('website_press_kit.press_kit_page', {
            'kit': kit, 'events': kit._upcoming_events() if kit.show_events else [],
        })

    @http.route('/press-kit/photo/<int:photo_id>', type='http', auth='public', website=True, sitemap=False)
    def press_kit_photo(self, photo_id, download=None, **kwargs):
        """A photo of the published kit: shown at web size, downloaded at full size."""
        kit = self._kit()
        photo = request.env['website.press.kit.photo'].sudo().browse(photo_id).exists()
        if not kit or not photo or photo.kit_id != kit:
            raise request.not_found()
        field = 'image_full' if download else 'image_display'
        stream = request.env['ir.binary']._get_image_stream_from(
            photo, field, filename=photo._download_name(photo))
        return stream.get_response(as_attachment=bool(download))

    @http.route('/press-kit/rider', type='http', auth='public', website=True, sitemap=False)
    def press_kit_rider(self, **kwargs):
        kit = self._kit()
        if not kit or not kit.rider:
            raise request.not_found()
        stream = request.env['ir.binary']._get_stream_from(
            kit, 'rider', filename=kit.rider_filename or 'technical-rider')
        return stream.get_response(as_attachment=True)
