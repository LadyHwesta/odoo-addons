# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDebrandingBundle(TransactionCase):

    def _installed(self, name):
        return self.env['ir.module.module'].search([('name', '=', name)]).state == 'installed'

    def test_the_general_debranding_is_installed(self):
        for name in ('disable_odoo_online', 'remove_odoo_enterprise', 'mail_debranding', 'portal_debranding'):
            with self.subTest(module=name):
                self.assertTrue(self._installed(name))

    def test_sales_and_website_follow_their_apps(self):
        """Installed with Sales and Website, or not at all."""
        for app, glue, oca in (('sale', 'debranding_bundle_sale', 'sale_portal_debranding'),
                               ('website', 'debranding_bundle_website', 'website_debranding')):
            with self.subTest(app=app):
                self.assertEqual(self._installed(glue), self._installed(app))
                self.assertEqual(self._installed(oca), self._installed(app))

    def test_accounting_labels_are_plain(self):
        if not self._installed('debranding_bundle_account'):
            self.skipTest('financial reports and statement import not installed')
        self.assertEqual(self.env.ref('account_financial_report.menu_oca_reports').name, 'Financial Reports')
        view = self.env.ref('account.account_journal_dashboard_kanban_view')
        combined = view.get_combined_arch()
        self.assertIn('Import File', combined)
        self.assertNotIn('(OCA)', combined)
        labels = dict(self.env['account.journal']._fields['bank_statements_source']._description_selection(self.env))
        self.assertNotIn('OCA', labels.get('file_import_oca', ''))
