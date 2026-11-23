# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = 'website'

    def _get_canonical_url(self):
        try:
            return super()._get_canonical_url()
        except ValueError as exc:
            # A path the strict URL join refuses (dot segments, "//host"):
            # only junk addresses, so their 404 page points at the home page.
            _logger.debug("No canonical URL for this path (%s); using the home page", exc)
            return self.get_base_url().rstrip('/') + '/'
