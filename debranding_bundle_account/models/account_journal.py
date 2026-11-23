# -*- coding: utf-8 -*-
from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Same (name-mangled) method name as core's and the statement import's,
    # so this extends theirs.
    def __get_bank_statements_available_sources(self):
        sources = super().__get_bank_statements_available_sources()
        return [(key, self.env._("Import File (%s)", label.rsplit('(', 1)[-1].rstrip(')'))
                 if key == 'file_import_oca' and '(' in label else label)
                for key, label in sources]
