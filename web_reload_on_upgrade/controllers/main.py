# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.tools.misc import hmac


class ReloadOnUpgrade(http.Controller):

    @http.route('/web_reload_on_upgrade/version', type='http', auth='user',
                methods=['GET'], readonly=True)
    def version(self):
        """The registry fingerprint the web client was started with
        (``session.registry_hash``), as the server has it now. It is
        worked out exactly as ``ir.http.session_info`` does, and changes
        whenever modules are installed or upgraded."""
        registry_hash = hmac(request.env(su=True), 'webclient-cache',
                             request.env.registry.registry_sequence)
        return request.make_json_response(
            {'registry_hash': registry_hash},
            headers=[('Cache-Control', 'no-store')])
