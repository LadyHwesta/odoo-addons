# -*- coding: utf-8 -*-
import re
from unittest.mock import MagicMock, patch

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireSmsPortal(HttpCase):

    def setUp(self):
        super().setUp()
        self.signalwire_client = MagicMock()
        patcher = patch(
            'odoo.addons.signalwire_voip.models.signalwire_server.'
            'SignalWireServer._get_client', return_value=self.signalwire_client)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.server = self.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        self.portal_user = self.env['res.users'].create({
            'name': 'Member Fred', 'login': 'fred_sms', 'password': 'fred_sms',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.own_subproject = self.env['signalwire.subproject'].create({
            'name': 'Freds Numbers', 'server_id': self.server.id,
            'account_sid': 'sub-fred', 'state': 'active',
            'partner_id': self.portal_user.partner_id.id,
        })
        self.own_number = self.env['signalwire.phone_number'].create({
            'name': '+13052808277', 'sid': 'pn-fred',
            'subproject_id': self.own_subproject.id,
        })
        other_partner = self.env['res.partner'].create({'name': 'Someone Else'})
        self.other_subproject = self.env['signalwire.subproject'].create({
            'name': 'Someone Elses Numbers', 'server_id': self.server.id,
            'account_sid': 'sub-other', 'state': 'active',
            'partner_id': other_partner.id,
        })
        self.other_number = self.env['signalwire.phone_number'].create({
            'name': '+13052808278', 'sid': 'pn-other',
            'subproject_id': self.other_subproject.id,
        })

    def _csrf_token(self):
        # These portal POST routes deliberately keep CSRF protection
        # on (auth='user' alone doesn't stop a cross-site request from
        # a logged-in user's own browser) - so, like a real browser,
        # the test fetches a real token from a rendered page first
        # rather than disabling the check to make posting easier.
        page = self.url_open('/my/sms')
        match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        self.assertTrue(match, "no csrf_token found on /my/sms")
        return match.group(1)

    def test_my_sms_page_shows_own_number_only(self):
        self.authenticate('fred_sms', 'fred_sms')

        resp = self.url_open('/my/sms')

        self.assertEqual(resp.status_code, 200)
        self.assertIn('+13052808277', resp.text)
        self.assertNotIn('+13052808278', resp.text)

    def test_portal_send_only_works_for_own_number(self):
        self.signalwire_client.compat_post.return_value = {'sid': 'sms-1', 'status': 'queued'}
        self.authenticate('fred_sms', 'fred_sms')
        csrf_token = self._csrf_token()

        self.url_open('/my/sms/send', data={
            'csrf_token': csrf_token, 'phone_number_id': self.other_number.id,
            'to': '+15551234567', 'body': 'should not send',
        })

        self.signalwire_client.compat_post.assert_not_called()

    def test_portal_send_works_for_own_number(self):
        self.signalwire_client.compat_post.return_value = {'sid': 'sms-1', 'status': 'queued'}
        self.authenticate('fred_sms', 'fred_sms')
        csrf_token = self._csrf_token()

        self.url_open('/my/sms/send', data={
            'csrf_token': csrf_token, 'phone_number_id': self.own_number.id,
            'to': '+15551234567', 'body': 'should send',
        })

        self.signalwire_client.compat_post.assert_called_once_with(
            'Accounts/sub-fred/Messages.json',
            From='+13052808277', To='+15551234567', Body='should send')

    def test_portal_can_set_own_webhook_url(self):
        self.authenticate('fred_sms', 'fred_sms')
        csrf_token = self._csrf_token()

        self.url_open('/my/sms/webhook', data={
            'csrf_token': csrf_token, 'phone_number_id': self.own_number.id,
            'sms_webhook_url': 'https://fred.example.com/hook',
        })

        self.assertEqual(self.own_number.sms_webhook_url, 'https://fred.example.com/hook')

    def test_portal_cannot_set_someone_elses_webhook_url(self):
        self.authenticate('fred_sms', 'fred_sms')
        csrf_token = self._csrf_token()

        self.url_open('/my/sms/webhook', data={
            'csrf_token': csrf_token, 'phone_number_id': self.other_number.id,
            'sms_webhook_url': 'https://fred.example.com/hook',
        })

        self.assertFalse(self.other_number.sms_webhook_url)

    def test_portal_can_issue_and_revoke_own_token(self):
        self.signalwire_client.project_post.return_value = {
            'id': 'tok-1', 'token': 'swapi_realsecret',
        }
        self.authenticate('fred_sms', 'fred_sms')
        csrf_token = self._csrf_token()

        self.url_open('/my/sms/token/issue', data={
            'csrf_token': csrf_token, 'phone_number_id': self.own_number.id,
        })

        token = self.env['signalwire.customer.token'].search(
            [('subproject_id', '=', self.own_subproject.id)])
        self.assertTrue(token)

        self.url_open('/my/sms/token/revoke', data={
            'csrf_token': csrf_token, 'token_id': token.id,
        })
        self.signalwire_client.project_delete.assert_called_once_with('project/tokens/tok-1')
        self.assertFalse(token.active)

    def test_portal_cannot_revoke_someone_elses_token(self):
        token = self.env['signalwire.customer.token'].create({
            'subproject_id': self.other_subproject.id,
            'signalwire_token_id': 'tok-other', 'token': 'swapi_othersecret',
        })
        self.authenticate('fred_sms', 'fred_sms')
        csrf_token = self._csrf_token()

        self.url_open('/my/sms/token/revoke', data={
            'csrf_token': csrf_token, 'token_id': token.id,
        })

        self.signalwire_client.project_delete.assert_not_called()
        self.assertTrue(token.active)
