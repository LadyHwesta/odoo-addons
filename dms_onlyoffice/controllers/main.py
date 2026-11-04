# -*- coding: utf-8 -*-
from odoo.addons.onlyoffice_odoo.controllers.controllers import Onlyoffice_Connector


class OnlyofficeConnector(Onlyoffice_Connector):

    def prepare_editor_values(self, attachment, access_token, can_write):
        # ONLYOFFICE's in-app route decides can_write from model-level rights,
        # so someone who can only read this record would get edit mode, and
        # then lose their work when the save is refused.
        can_write = can_write and attachment.has_access('write')
        return super().prepare_editor_values(attachment, access_token, can_write)
