# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireCallbackRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Portal Customer'})
        cls.agent = cls.env['res.users'].create({
            'name': 'Agent Smith', 'login': 'agent.smith@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref(
                    'signalwire_voip_click2call.group_signalwire_receptionist').id,
            ])],
        })

    def _request(self, **extra):
        vals = {'partner_id': self.partner.id, 'phone_number': '+15551234567'}
        vals.update(extra)
        return self.env['signalwire.callback_request'].create(vals)

    def test_create_defaults_to_pending(self):
        req = self._request()
        self.assertEqual(req.state, 'pending')

    def test_claim_sets_state_and_claimant(self):
        req = self._request()

        req.with_user(self.agent).action_claim()

        self.assertEqual(req.state, 'claimed')
        self.assertEqual(req.claimed_by_user_id, self.agent)

    def test_claim_schedules_a_callback_activity(self):
        req = self._request()

        req.with_user(self.agent).action_claim()

        activities = req.activity_ids.filtered(lambda a: a.user_id == self.agent)
        self.assertTrue(activities)

    def test_claiming_twice_raises(self):
        req = self._request()
        req.with_user(self.agent).action_claim()

        with self.assertRaises(UserError):
            req.with_user(self.agent).action_claim()

    def test_complete_closes_the_activity(self):
        req = self._request()
        req.with_user(self.agent).action_claim()

        req.with_user(self.agent).action_complete()

        self.assertEqual(req.state, 'completed')
        open_activities = req.activity_ids.filtered(lambda a: a.user_id == self.agent)
        self.assertFalse(open_activities)
