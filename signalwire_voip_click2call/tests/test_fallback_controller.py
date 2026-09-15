# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestFallbackController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.teammate = cls.env['res.users'].create({
            'name': 'Backup Agent', 'login': 'backup.agent@example.com',
            'voip_username': 'user_backup',
        })
        cls.user = cls.env['res.users'].create({
            'name': 'Jane Agent', 'login': 'jane.agent@example.com',
            'voip_username': 'user_jane',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.subproject.id, 'assigned_user_id': cls.user.id,
        })

    def _fallback_url(self, step=None):
        url = f'/signalwire/voice/fallback/{self.user.id}/{self.number.id}'
        if step:
            url += f'?step={step}'
        return url

    def test_completed_status_ends_the_chain(self):
        response = self.url_open(self._fallback_url(), data={'DialCallStatus': 'completed'})
        self.assertNotIn('<Dial', response.text)
        self.assertNotIn('<Reject', response.text)

    def test_default_config_goes_straight_to_voicemail(self):
        # voicemail defaults to enabled (the guaranteed last resort),
        # so a totally unconfigured user still doesn't just reject.
        response = self.url_open(self._fallback_url(), data={'DialCallStatus': 'no-answer'})
        self.assertIn('<Record', response.text)

    def test_nothing_configured_at_all_rejects(self):
        self.user.signalwire_voicemail_enabled = False
        response = self.url_open(self._fallback_url(), data={'DialCallStatus': 'no-answer'})
        self.assertIn('<Reject', response.text)

    def test_forward_configured_dials_the_saved_number(self):
        number = self.env['signalwire.forwarding.number'].create({
            'user_id': self.user.id, 'name': 'Cell', 'phone_number': '+15559876543',
        })
        self.user.signalwire_active_forward_id = number.id

        response = self.url_open(self._fallback_url(), data={'DialCallStatus': 'no-answer'})

        self.assertIn('<Number>+15559876543</Number>', response.text)
        self.assertIn('step=forward', response.text)

    def test_forward_step_falls_through_to_group(self):
        self.user.signalwire_ring_group_ids = [(6, 0, [self.teammate.id])]

        response = self.url_open(
            self._fallback_url(step='forward'), data={'DialCallStatus': 'no-answer'})

        self.assertIn('sip:user_backup@example.sip.signalwire.com', response.text)

    def test_group_only_rings_teammates_with_a_softphone(self):
        no_softphone_teammate = self.env['res.users'].create({
            'name': 'No Softphone', 'login': 'no.softphone@example.com',
        })
        self.user.signalwire_ring_group_ids = [
            (6, 0, [self.teammate.id, no_softphone_teammate.id])]

        response = self.url_open(
            self._fallback_url(step='forward'), data={'DialCallStatus': 'no-answer'})

        self.assertIn('user_backup', response.text)
        self.assertNotIn('No Softphone', response.text)

    def test_group_step_falls_through_to_voicemail(self):
        self.user.signalwire_ring_group_ids = [(6, 0, [self.teammate.id])]

        response = self.url_open(
            self._fallback_url(step='group'), data={'DialCallStatus': 'no-answer'})

        self.assertIn('<Record', response.text)
        self.assertIn(f'/signalwire/voice/voicemail_complete/{self.user.id}/{self.number.id}',
                       response.text)

    def test_forward_and_group_both_configured_uses_forward_first(self):
        number = self.env['signalwire.forwarding.number'].create({
            'user_id': self.user.id, 'name': 'Cell', 'phone_number': '+15559876543',
        })
        self.user.write({
            'signalwire_active_forward_id': number.id,
            'signalwire_ring_group_ids': [(6, 0, [self.teammate.id])],
        })

        response = self.url_open(self._fallback_url(), data={'DialCallStatus': 'no-answer'})

        self.assertIn('<Number>+15559876543</Number>', response.text)
        self.assertNotIn('user_backup', response.text)
