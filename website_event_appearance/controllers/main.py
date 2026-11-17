# -*- coding: utf-8 -*-
from werkzeug.exceptions import NotFound

from odoo import http

from odoo.addons.website_event.controllers.main import WebsiteEventController


class WebsiteEventAppearanceController(WebsiteEventController):
    """No registrations for an appearance, even posted directly: the host
    takes them."""

    @http.route()
    def registration_new(self, event, **post):
        if event.is_appearance:
            raise NotFound()
        return super().registration_new(event, **post)

    @http.route()
    def registration_confirm(self, event, **post):
        if event.is_appearance:
            raise NotFound()
        return super().registration_confirm(event, **post)
