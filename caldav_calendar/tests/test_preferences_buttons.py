# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPreferencesButtons(TransactionCase):
    """Edit, Remove and Add from the Preferences list, own accounts only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = [(6, 0, [cls.env.ref('base.group_user').id])]
        cls.me = cls.env['res.users'].create({'name': 'Me', 'login': 'me.caldav@example.com', 'group_ids': group})
        cls.other = cls.env['res.users'].create({'name': 'Other', 'login': 'other.caldav@example.com', 'group_ids': group})
        Account = cls.env['caldav.account']
        cls.mine = Account.create({'name': 'Mine', 'user_id': cls.me.id, 'read_only': True,
                                   'url': 'https://dav.example.com/me/calendar/'})
        cls.theirs = Account.create({'name': 'Theirs', 'user_id': cls.other.id, 'read_only': True,
                                     'url': 'https://dav.example.com/other/calendar/'})

    def test_edit_opens_my_account_in_a_popup(self):
        action = self.mine.with_user(self.me).action_open_settings()
        self.assertEqual((action['res_id'], action['target']), (self.mine.id, 'new'))

    def test_add_opens_a_new_account_for_me(self):
        action = self.me.with_user(self.me).action_caldav_add_account()
        self.assertFalse(action['res_id'])
        self.assertEqual(action['context']['default_user_id'], self.me.id)

    def test_remove_my_account_but_never_someone_elses(self):
        self.mine.with_user(self.me).action_remove()
        self.assertFalse(self.mine.exists())
        with self.assertRaises(AccessError):
            self.theirs.with_user(self.me).action_remove()
        self.assertTrue(self.theirs.exists())
