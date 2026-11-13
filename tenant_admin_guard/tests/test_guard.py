# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTenantAdminGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider_group = cls.env.ref('tenant_admin_guard.group_provider_admin')
        cls.provider = cls.env.ref('base.user_admin')
        cls.customer_admin = cls.env['res.users'].create({
            'name': 'Customer Admin', 'login': 'customer-admin@example.com',
            'email': 'customer-admin@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_system').id])],
        })
        cls.staff = cls.env['res.users'].create({
            'name': 'Staff', 'login': 'staff@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })
        cls.module = cls.env['ir.module.module'].search([('state', '=', 'uninstalled')], limit=1)

    def as_customer(self, model):
        return self.env[model].with_user(self.customer_admin)

    # -- the role -------------------------------------------------------

    def test_builtin_admin_is_the_technical_administrator(self):
        self.assertIn(self.provider, self.provider_group.user_ids)
        self.assertTrue(self.provider.has_group('base.group_system'))

    def test_customer_admin_keeps_settings(self):
        self.assertTrue(self.customer_admin.has_group('base.group_system'))
        self.assertFalse(self.customer_admin.has_group('tenant_admin_guard.group_provider_admin'))
        settings = self.as_customer('res.config.settings').create({})
        settings.execute()  # nothing that installs an app: allowed

    # -- apps -------------------------------------------------------------

    def test_customer_admin_cant_install_or_remove_apps(self):
        module = self.module.with_user(self.customer_admin)
        for method in ('button_install', 'button_immediate_install', 'button_upgrade',
                       'button_uninstall', 'button_immediate_uninstall', 'update_list'):
            with self.subTest(method=method), self.assertRaisesRegex(AccessError, 'hosting provider'):
                getattr(module, method)()
        with self.assertRaises(AccessError):
            module.write({'state': 'to install'})
        with self.assertRaises(AccessError):
            self.as_customer('base.module.upgrade').create({}).upgrade_module()

    def test_settings_that_install_an_app_are_refused(self):
        settings = self.as_customer('res.config.settings').create({})
        field = next((name for name, f in settings._fields.items()
                      if name.startswith('module_') and f.type == 'boolean'
                      and self.env['ir.module.module'].search(
                          [('name', '=', name[7:]), ('state', '=', 'uninstalled')])), None)
        if not field:
            self.skipTest("no uninstalled module_ setting in this database")
        settings[field] = True
        with self.assertRaisesRegex(AccessError, 'adds or removes an app'):
            settings.execute()

    def test_internal_code_can_still_install(self):
        # e.g. a company's localization, installed by Odoo itself with sudo
        self.module.with_user(self.customer_admin).sudo().button_install()
        self.assertEqual(self.module.state, 'to install')

    def test_apps_and_technical_menus_are_provider_only(self):
        apps, technical = self.env.ref('base.menu_management'), self.env.ref('base.menu_custom')
        # Even when another module opens Apps to everyone, as
        # base_install_request does.
        apps.group_ids = False
        Menu = self.env['ir.ui.menu']
        Menu.env.registry.clear_cache()
        customer = Menu.with_user(self.customer_admin)._visible_menu_ids(debug=True)
        self.assertNotIn(apps.id, customer)
        self.assertNotIn(technical.id, customer)
        self.assertFalse(set(technical.child_id.ids) & customer)
        provider = Menu.with_user(self.provider)._visible_menu_ids(debug=True)
        self.assertIn(apps.id, provider)
        self.assertIn(technical.id, provider)

    # -- the technical administrator's account ----------------------------

    def test_customer_admin_cant_take_over_the_provider_account(self):
        provider = self.provider.with_user(self.customer_admin)
        for vals in ({'password': 'x' * 12}, {'login': 'mine'}, {'email': 'me@example.com'},
                     {'active': False}):
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                provider.write(vals)
        with self.assertRaises(AccessError):
            provider.partner_id.with_user(self.customer_admin).write({'email': 'me@example.com'})
        with self.assertRaises(AccessError):
            provider.unlink()

    def test_customer_admin_manages_their_own_users(self):
        staff = self.staff.with_user(self.customer_admin)
        staff.write({'login': 'staff2@example.com', 'email': 'staff2@example.com', 'active': False})
        self.assertEqual(self.staff.login, 'staff2@example.com')

    # One refusal per test: a refused write's pending changes stay in the
    # test's record cache, where a real request would have rolled back.

    def test_role_cant_be_added_to_a_user(self):
        with self.assertRaisesRegex(AccessError, 'technical administrator role'):
            self.staff.with_user(self.customer_admin).write(
                {'group_ids': [Command.link(self.provider_group.id)]})

    def test_customer_admin_cant_add_themselves_to_the_role(self):
        with self.assertRaises(AccessError):
            self.provider_group.with_user(self.customer_admin).write(
                {'user_ids': [Command.link(self.customer_admin.id)]})

    def test_role_cant_be_implied_by_another_group(self):
        employees = self.env.ref('base.group_user').with_user(self.customer_admin)
        with self.assertRaises(AccessError):
            employees.write({'implied_ids': [Command.link(self.provider_group.id)]})

    def test_role_cant_be_given_to_a_new_user(self):
        with self.assertRaises(AccessError):
            self.as_customer('res.users').create({
                'name': 'Sneaky', 'login': 'sneaky@example.com',
                'group_ids': [Command.set([self.provider_group.id])]})

    def test_provider_can_hand_out_the_role(self):
        self.staff.with_user(self.provider).write(
            {'group_ids': [Command.link(self.provider_group.id)]})
        self.assertTrue(self.staff.has_group('tenant_admin_guard.group_provider_admin'))

    # -- code ---------------------------------------------------------------

    def test_customer_admin_cant_write_code(self):
        model = self.env.ref('base.model_res_partner')
        with self.assertRaisesRegex(AccessError, 'Writing code'):
            self.as_customer('ir.actions.server').create(
                {'name': 'x', 'model_id': model.id, 'state': 'code', 'code': 'pass'})
        with self.assertRaises(AccessError):
            self.as_customer('ir.model.fields').create({
                'name': 'x_total', 'model_id': model.id, 'ttype': 'integer',
                'compute': "for r in self: r['x_total'] = 1"})

    def test_customer_admin_can_make_actions_that_dont_run_code(self):
        model = self.env.ref('base.model_res_partner')
        action = self.as_customer('ir.actions.server').create(
            {'name': 'Mark', 'model_id': model.id, 'state': 'object_write',
             'code': '# default text the form sends'})
        action.name = 'Mark them'
        with self.assertRaises(AccessError):
            action.state = 'code'
