# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


def _make_number(env, name='+12084449665', sid='pn-123'):
    server = env['signalwire.server'].create({
        'name': 'Test SignalWire', 'space': 'example.signalwire.com',
        'sip_domain': 'example-abc123.sip.signalwire.com',
        'project_id': 'pid123', 'api_token': 'tok456',
    })
    subproject = env['signalwire.subproject'].create({
        'name': 'Internal Team', 'server_id': server.id,
        'account_sid': 'sub-abc', 'state': 'active',
    })
    return env['signalwire.phone_number'].create({
        'name': name, 'sid': sid, 'subproject_id': subproject.id,
    })


@tagged('post_install', '-at_install')
class TestSignalWireVoicemailProject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.number = _make_number(cls.env)
        cls.partner = cls.env['res.partner'].create({
            'name': 'Caller Contact', 'phone': '+15551234567'})
        cls.matched_voicemail = cls.env['signalwire.voicemail'].create({
            'phone_number_id': cls.number.id, 'user_id': cls.env.user.id,
            'from_number': '+15551234567', 'duration': 20,
            'partner_id': cls.partner.id,
        })
        cls.unmatched_voicemail = cls.env['signalwire.voicemail'].create({
            'phone_number_id': cls.number.id, 'user_id': cls.env.user.id,
            'from_number': '+19995550000', 'duration': 15,
        })

    def test_create_task_raises_without_a_matched_partner(self):
        with self.assertRaises(UserError):
            self.unmatched_voicemail.action_create_task()

    def test_create_task_returns_the_right_context(self):
        action = self.matched_voicemail.action_create_task()

        self.assertEqual(action['res_model'], 'project.task')
        self.assertEqual(action['context']['default_partner_id'], self.partner.id)
        self.assertIn('+15551234567', action['context']['default_name'])
        self.assertIn(
            'Voicemail from +15551234567', action['context']['default_description'])

    def test_create_task_leaves_project_blank_with_no_matching_project(self):
        action = self.matched_voicemail.action_create_task()

        self.assertFalse(action['context']['default_project_id'])

    def test_create_task_prefills_the_project_when_exactly_one_match(self):
        project = self.env['project.project'].create({
            'name': 'Caller Contact Project', 'partner_id': self.partner.id,
        })

        action = self.matched_voicemail.action_create_task()

        self.assertEqual(action['context']['default_project_id'], project.id)

    def test_create_task_leaves_project_blank_with_multiple_matches(self):
        self.env['project.project'].create({
            'name': 'First Project', 'partner_id': self.partner.id})
        self.env['project.project'].create({
            'name': 'Second Project', 'partner_id': self.partner.id})

        action = self.matched_voicemail.action_create_task()

        self.assertFalse(action['context']['default_project_id'])

    def test_attach_raises_without_a_matched_partner(self):
        with self.assertRaises(UserError):
            self.unmatched_voicemail.action_attach_to_project_or_task()

    def test_attach_opens_the_wizard(self):
        action = self.matched_voicemail.action_attach_to_project_or_task()

        self.assertEqual(action['res_model'], 'signalwire.voicemail.attach.project.wizard')
        self.assertEqual(action['context']['default_voicemail_id'], self.matched_voicemail.id)

    def test_cannot_set_both_project_and_task_at_once(self):
        project = self.env['project.project'].create({'name': 'A Project'})
        task = self.env['project.task'].create({'name': 'A Task'})

        with self.assertRaises(ValidationError):
            self.matched_voicemail.write({'project_id': project.id, 'task_id': task.id})

    def test_buttons_are_hidden_once_attached_to_a_task(self):
        task = self.env['project.task'].create({'name': 'A Task'})
        self.matched_voicemail.task_id = task.id

        view = self.matched_voicemail.get_view(
            view_id=self.env.ref(
                'signalwire_voip_click2call.view_signalwire_voicemail_form').id,
            view_type='form')

        self.assertIn('not partner_id or project_id or task_id', view['arch'])


@tagged('post_install', '-at_install')
class TestSignalWireVoicemailAttachProjectWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.number = _make_number(cls.env)
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
        cls.matching_project = cls.env['project.project'].create({
            'name': 'Matching Project', 'partner_id': cls.partner.id})
        cls.other_project = cls.env['project.project'].create({
            'name': 'Other Project', 'partner_id': cls.other_partner.id})
        cls.matching_task = cls.env['project.task'].create({
            'name': 'Matching Task', 'partner_id': cls.partner.id})
        cls.other_task = cls.env['project.task'].create({
            'name': 'Other Task', 'partner_id': cls.other_partner.id})

    def test_project_domain_only_offers_the_matched_partners_projects(self):
        wizard = self.env['signalwire.voicemail.attach.project.wizard'].create({
            'voicemail_id': self.voicemail.id, 'attach_mode': 'project',
            'project_id': self.matching_project.id,
        })

        self.assertEqual(wizard.partner_id, self.partner)

    def test_task_domain_only_offers_the_matched_partners_tasks(self):
        wizard = self.env['signalwire.voicemail.attach.project.wizard'].create({
            'voicemail_id': self.voicemail.id, 'attach_mode': 'task',
            'task_id': self.matching_task.id,
        })

        self.assertEqual(wizard.partner_id, self.partner)

    def test_attach_to_project_posts_and_sets_the_link(self):
        wizard = self.env['signalwire.voicemail.attach.project.wizard'].create({
            'voicemail_id': self.voicemail.id, 'attach_mode': 'project',
            'project_id': self.matching_project.id,
        })

        wizard.action_attach()

        self.assertEqual(self.voicemail.project_id, self.matching_project)
        self.assertFalse(self.voicemail.task_id)
        self.assertTrue(any(
            'Voicemail from' in (msg.body or '')
            for msg in self.matching_project.message_ids))
        self.assertIn(
            self.voicemail.recording_attachment_id,
            self.matching_project.message_ids.mapped('attachment_ids'))

    def test_attach_to_task_posts_and_sets_the_link(self):
        wizard = self.env['signalwire.voicemail.attach.project.wizard'].create({
            'voicemail_id': self.voicemail.id, 'attach_mode': 'task',
            'task_id': self.matching_task.id,
        })

        wizard.action_attach()

        self.assertEqual(self.voicemail.task_id, self.matching_task)
        self.assertFalse(self.voicemail.project_id)
        self.assertTrue(any(
            'Voicemail from' in (msg.body or '')
            for msg in self.matching_task.message_ids))

    def test_attach_to_project_without_choosing_one_raises(self):
        wizard = self.env['signalwire.voicemail.attach.project.wizard'].create({
            'voicemail_id': self.voicemail.id, 'attach_mode': 'project',
        })

        with self.assertRaises(UserError):
            wizard.action_attach()

    def test_attach_to_task_without_choosing_one_raises(self):
        wizard = self.env['signalwire.voicemail.attach.project.wizard'].create({
            'voicemail_id': self.voicemail.id, 'attach_mode': 'task',
        })

        with self.assertRaises(UserError):
            wizard.action_attach()
