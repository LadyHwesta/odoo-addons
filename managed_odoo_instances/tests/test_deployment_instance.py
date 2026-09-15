# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDeploymentInstance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Example Nonprofit'})
        cls.shared_server = cls.env['deployment.server'].create({
            'name': 'Shared Server', 'hostname': 'shared.example.com',
            'kind': 'shared', 'agent_url': 'https://shared.example.com:8765',
            'agent_token': 'shared-token', 'bootstrap_state': 'not_needed',
        })
        cls.dedicated_server_pending = cls.env['deployment.server'].create({
            'name': 'Dedicated - Pending', 'hostname': 'vps1.example.com',
            'kind': 'dedicated', 'partner_id': cls.partner.id,
            'agent_url': 'https://vps1.example.com:8765', 'bootstrap_state': 'pending',
        })
        cls.dedicated_server_done = cls.env['deployment.server'].create({
            'name': 'Dedicated - Done', 'hostname': 'vps2.example.com',
            'kind': 'dedicated', 'partner_id': cls.partner.id,
            'agent_url': 'https://vps2.example.com:8765', 'agent_token': 'vps2-token',
            'bootstrap_state': 'done',
        })
        cls.upcloud_account = cls.env['upcloud.account'].create({
            'name': 'Test UpCloud Account', 'api_token': 'ucat_test',
            'ssh_public_key': 'ssh-ed25519 AAAA...',
        })
        cls.dedicated_server_upcloud = cls.env['deployment.server'].create({
            'name': 'Dedicated - UpCloud', 'hostname': 'pending.example.com',
            'kind': 'dedicated', 'partner_id': cls.partner.id,
            'agent_url': 'https://vps3.example.com:8765', 'bootstrap_state': 'pending',
            'vps_provider': 'upcloud', 'upcloud_account_id': cls.upcloud_account.id,
        })
        cls.free_app = cls.env['deployment.app'].create({
            'name': 'Test Suite', 'module_names': 'base,mail',
        })
        cls.product = cls.env['product.template'].create({
            'name': 'Managed Nonprofit Suite', 'list_price': 99.0,
        })
        cls.billable_app = cls.env['deployment.app'].create({
            'name': 'Nonprofit Suite (Managed)', 'module_names': 'nonprofit_base,donation',
            'product_template_id': cls.product.id,
        })

    def _instance(self, server, **extra):
        vals = {
            'partner_id': self.partner.id, 'server_id': server.id,
            'domain': 'example.org', 'db_name': 'example_org',
            'admin_email': 'owner@example.org', 'company_name': 'Example Nonprofit',
        }
        vals.update(extra)
        return self.env['deployment.instance'].create(vals)

    # -- validation --------------------------------------------------------

    def test_rejects_an_invalid_domain(self):
        with self.assertRaises(ValidationError):
            self._instance(self.shared_server, domain='not a domain')

    def test_rejects_an_invalid_db_name(self):
        with self.assertRaises(ValidationError):
            self._instance(self.shared_server, db_name='1-starts-with-digit')

    # -- action_request: contract + project generation ----------------------

    def test_request_on_a_shared_server_skips_bootstrap_tasks(self):
        instance = self._instance(self.shared_server, app_ids=[(6, 0, [self.free_app.id])])

        instance.action_request()

        self.assertTrue(instance.contract_id)
        self.assertFalse(instance.contract_id.contract_line_ids, "no billing until live")
        self.assertEqual(len(instance.project_id.task_ids), 5)
        self.assertEqual(instance.state, 'provisioning')

    def test_request_on_a_pending_dedicated_server_includes_bootstrap_tasks(self):
        instance = self._instance(self.dedicated_server_pending)

        instance.action_request()

        self.assertEqual(len(instance.project_id.task_ids), 8)
        self.assertEqual(instance.state, 'bootstrap_pending')
        bootstrap_task = instance.project_id.task_ids.filtered(
            lambda t: 'bootstrap script' in t.name)
        self.assertTrue(bootstrap_task.attachment_ids)
        self.assertEqual(bootstrap_task.attachment_ids.name, 'bootstrap.sh')

    def test_request_on_an_upcloud_dedicated_server_adds_a_create_vps_task(self):
        instance = self._instance(self.dedicated_server_upcloud)

        instance.action_request()

        self.assertEqual(len(instance.project_id.task_ids), 9, "3 bootstrap + 1 VPS + 5 deploy")
        create_vps_task = instance.project_id.task_ids.filtered(
            lambda t: 'Create the UpCloud VPS' in t.name)
        self.assertTrue(create_vps_task)
        # comes before "Confirm server access"
        confirm_access_task = instance.project_id.task_ids.filtered(
            lambda t: 'Confirm server access' in t.name)
        self.assertLess(create_vps_task.sequence, confirm_access_task.sequence)

    def test_request_on_an_already_bootstrapped_dedicated_server_skips_bootstrap_tasks(self):
        instance = self._instance(self.dedicated_server_done)

        instance.action_request()

        self.assertEqual(len(instance.project_id.task_ids), 5)
        self.assertEqual(instance.state, 'provisioning')

    def test_request_does_not_duplicate_the_contract_on_a_second_call(self):
        instance = self._instance(self.shared_server)
        instance.action_request()
        first_contract = instance.contract_id

        instance.action_request()

        self.assertEqual(instance.contract_id, first_contract)

    # -- the deployment actions call through to the agent client ------------

    def test_create_vhost_calls_the_agent_with_the_right_args(self):
        instance = self._instance(self.shared_server)
        instance.action_request()
        mock_client = MagicMock()
        with patch(
                'odoo.addons.managed_odoo_instances.models.deployment_server.'
                'DeploymentServer._get_client', return_value=mock_client):
            instance.action_create_vhost()

        mock_client.create_vhost.assert_called_once_with('example.org', 'example_org')

    def test_create_database_passes_the_combined_module_list(self):
        instance = self._instance(self.shared_server, app_ids=[(6, 0, [
            self.free_app.id, self.billable_app.id])])
        instance.action_request()
        mock_client = MagicMock()
        with patch(
                'odoo.addons.managed_odoo_instances.models.deployment_server.'
                'DeploymentServer._get_client', return_value=mock_client):
            instance.action_create_database()

        mock_client.create_database.assert_called_once_with(
            'example_org', ['base', 'mail', 'nonprofit_base', 'donation'],
            'owner@example.org', 'Example Nonprofit')

    def test_all_module_names_deduplicates_across_apps(self):
        overlapping_app = self.env['deployment.app'].create({
            'name': 'Overlap', 'module_names': 'base,sale',
        })
        instance = self._instance(self.shared_server, app_ids=[(6, 0, [
            self.free_app.id, overlapping_app.id])])

        self.assertEqual(instance._all_module_names(), ['base', 'mail', 'sale'])

    # -- action_mark_live: where billing actually starts ---------------------

    def test_mark_live_creates_a_contract_line_per_billable_app(self):
        instance = self._instance(self.shared_server, app_ids=[(6, 0, [
            self.free_app.id, self.billable_app.id])])
        instance.action_request()

        instance.action_mark_live()

        self.assertEqual(instance.state, 'live')
        self.assertEqual(len(instance.contract_id.contract_line_ids), 1, "only the billable app")
        line = instance.contract_id.contract_line_ids
        self.assertEqual(line.price_unit, 99.0)
        self.assertEqual(line.recurring_invoicing_type, 'pre-paid')

    def test_mark_live_with_no_billable_apps_creates_no_lines(self):
        instance = self._instance(self.shared_server, app_ids=[(6, 0, [self.free_app.id])])
        instance.action_request()

        instance.action_mark_live()

        self.assertEqual(instance.state, 'live')
        self.assertFalse(instance.contract_id.contract_line_ids)

    def test_mark_live_twice_does_not_duplicate_lines(self):
        instance = self._instance(self.shared_server, app_ids=[(6, 0, [self.billable_app.id])])
        instance.action_request()

        instance.action_mark_live()
        instance.action_mark_live()

        self.assertEqual(len(instance.contract_id.contract_line_ids), 1)

    # -- suspend / cancel -----------------------------------------------------

    def test_cancel_ends_the_open_contract_line(self):
        from datetime import date
        instance = self._instance(self.shared_server, app_ids=[(6, 0, [self.billable_app.id])])
        instance.action_request()
        instance.action_mark_live()
        line = instance.contract_id.contract_line_ids
        self.assertFalse(line.date_end)

        instance.action_cancel()

        self.assertEqual(instance.state, 'cancelled')
        self.assertEqual(line.date_end, date.today())

    def test_suspend_only_applies_to_live_instances(self):
        instance = self._instance(self.shared_server)
        instance.action_request()  # still 'provisioning'

        instance.action_suspend()

        self.assertEqual(instance.state, 'provisioning', "suspend is a no-op unless live")
