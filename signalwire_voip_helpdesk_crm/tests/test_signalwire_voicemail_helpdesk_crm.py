# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSignalWireVoicemailHelpdeskCrm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env['signalwire.server'].create({
            'name': 'Test SignalWire', 'space': 'example.signalwire.com',
            'sip_domain': 'example-abc123.sip.signalwire.com',
            'project_id': 'pid123', 'api_token': 'tok456',
        })
        cls.subproject = cls.env['signalwire.subproject'].create({
            'name': 'Internal Team', 'server_id': cls.server.id,
            'account_sid': 'sub-abc', 'state': 'active',
        })
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123', 'subproject_id': cls.subproject.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Caller Contact', 'phone': '+15551234567'})
        cls.other_partner = cls.env['res.partner'].create({
            'name': 'Someone Else', 'phone': '+15559998888'})
        cls.matched_voicemail = cls.env['signalwire.voicemail'].create({
            'phone_number_id': cls.number.id,
            'user_id': cls.env.user.id,
            'from_number': '+15551234567', 'duration': 20,
            'partner_id': cls.partner.id,
        })
        cls.unmatched_voicemail = cls.env['signalwire.voicemail'].create({
            'phone_number_id': cls.number.id,
            'user_id': cls.env.user.id,
            'from_number': '+19995550000', 'duration': 15,
        })

    def test_create_ticket_raises_without_a_matched_partner(self):
        with self.assertRaises(UserError):
            self.unmatched_voicemail.action_create_helpdesk_ticket()

    def test_create_ticket_returns_the_right_context(self):
        action = self.matched_voicemail.action_create_helpdesk_ticket()

        self.assertEqual(action['res_model'], 'helpdesk.ticket')
        self.assertEqual(action['context']['default_partner_id'], self.partner.id)
        self.assertIn('+15551234567', action['context']['default_name'])
        self.assertIn(
            'Voicemail from +15551234567', action['context']['default_description'])

    def test_create_lead_works_without_a_matched_partner(self):
        action = self.unmatched_voicemail.action_create_lead()

        self.assertEqual(action['res_model'], 'crm.lead')
        self.assertNotIn('default_partner_id', action['context'])

    def test_create_lead_includes_the_matched_partner(self):
        action = self.matched_voicemail.action_create_lead()

        self.assertEqual(action['context']['default_partner_id'], self.partner.id)

    def test_attach_to_ticket_raises_without_a_matched_partner(self):
        with self.assertRaises(UserError):
            self.unmatched_voicemail.action_attach_to_ticket()

    def test_attach_to_ticket_opens_the_wizard(self):
        action = self.matched_voicemail.action_attach_to_ticket()

        self.assertEqual(action['res_model'], 'signalwire.voicemail.attach.ticket.wizard')
        self.assertEqual(action['context']['default_voicemail_id'], self.matched_voicemail.id)


@tagged('post_install', '-at_install')
class TestSignalWireVoicemailAttachTicketWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.number = cls.env['signalwire.phone_number'].create({
            'name': '+12084449665', 'sid': 'pn-123',
            'subproject_id': cls.env['signalwire.subproject'].create({
                'name': 'Internal Team',
                'server_id': cls.env['signalwire.server'].create({
                    'name': 'Test SignalWire', 'space': 'example.signalwire.com',
                    'sip_domain': 'example-abc123.sip.signalwire.com',
                    'project_id': 'pid123', 'api_token': 'tok456',
                }).id,
                'account_sid': 'sub-abc', 'state': 'active',
            }).id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Caller Contact', 'phone': '+15551234567'})
        cls.other_partner = cls.env['res.partner'].create({'name': 'Someone Else'})
        cls.voicemail = cls.env['signalwire.voicemail'].create({
            'phone_number_id': cls.number.id, 'user_id': cls.env.user.id,
            'from_number': '+15551234567', 'duration': 20,
            'partner_id': cls.partner.id,
            'recording_attachment_id': cls.env['ir.attachment'].create({
                'name': 'vm.mp3', 'type': 'binary', 'raw': b'audio',
                'mimetype': 'audio/mpeg',
            }).id,
        })
        cls.matching_ticket = cls.env['helpdesk.ticket'].create({
            'name': 'Existing issue', 'description': '<p>desc</p>',
            'partner_id': cls.partner.id,
        })
        cls.other_ticket = cls.env['helpdesk.ticket'].create({
            'name': 'Someone else\'s ticket', 'description': '<p>desc</p>',
            'partner_id': cls.other_partner.id,
        })

    def test_ticket_domain_only_offers_the_matched_partners_tickets(self):
        wizard = self.env['signalwire.voicemail.attach.ticket.wizard'].create({
            'voicemail_id': self.voicemail.id, 'ticket_id': self.matching_ticket.id,
        })

        self.assertEqual(wizard.partner_id, self.partner)

    def test_attach_posts_to_the_tickets_chatter_and_attaches_the_recording(self):
        wizard = self.env['signalwire.voicemail.attach.ticket.wizard'].create({
            'voicemail_id': self.voicemail.id, 'ticket_id': self.matching_ticket.id,
        })

        wizard.action_attach()

        self.assertTrue(any(
            'Voicemail from' in (msg.body or '')
            for msg in self.matching_ticket.message_ids))
        self.assertIn(
            self.voicemail.recording_attachment_id,
            self.matching_ticket.message_ids.mapped('attachment_ids'))

    def test_attach_sets_the_voicemails_own_ticket_link(self):
        wizard = self.env['signalwire.voicemail.attach.ticket.wizard'].create({
            'voicemail_id': self.voicemail.id, 'ticket_id': self.matching_ticket.id,
        })

        wizard.action_attach()

        self.assertEqual(self.voicemail.helpdesk_ticket_id, self.matching_ticket)

    def test_buttons_are_hidden_once_attached_to_a_ticket(self):
        self.voicemail.helpdesk_ticket_id = self.matching_ticket.id

        view = self.voicemail.get_view(
            view_id=self.env.ref(
                'signalwire_voip_click2call.view_signalwire_voicemail_form').id,
            view_type='form')

        self.assertIn(
            'not partner_id or helpdesk_ticket_id', view['arch'])
