# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

CLIENT = 'odoo.addons.caldav_calendar.models.caldav_account.CalDAVAccount._caldav_get_client'


@tagged('post_install', '-at_install')
class TestDiscovery(TransactionCase):
    """Discover Calendars lists what the server has and fills in the URL.
    It used to fail before showing anything (found live 2026-11-16): the
    picker's choice was a required database column, but the picker is
    created before anyone chooses."""

    def setUp(self):
        super().setUp()
        self.account = self.env['caldav.account'].create({
            'name': 'Calendar', 'user_id': self.env.uid, 'discovery_url': 'https://dav.example.com/',
            'username': 'me@example.com', 'password': 'secret'})
        self.client = MagicMock()
        self.startPatcher(patch(CLIENT, return_value=self.client))

    def test_several_calendars_open_the_picker_with_the_first_chosen(self):
        self.client.discover_calendars.return_value = [
            {'display_name': 'Calendar', 'url': 'https://dav.example.com/me/calendar/'},
            {'display_name': 'Work', 'url': 'https://dav.example.com/me/work/'}]
        action = self.account.action_caldav_discover_calendars()
        wizard = self.env['caldav.calendar.select'].browse(action['res_id'])
        self.assertEqual(len(wizard.line_ids), 2)
        self.assertEqual(wizard.selected_line_id.name, 'Calendar')
        wizard.selected_line_id = wizard.line_ids[1]
        wizard.action_confirm()
        self.assertEqual(self.account.url, 'https://dav.example.com/me/work/')
        self.assertEqual(self.account.name, 'Work')

    def test_one_calendar_is_used_straight_away(self):
        self.client.discover_calendars.return_value = [
            {'display_name': 'Calendar', 'url': 'https://dav.example.com/me/calendar/'}]
        action = self.account.action_caldav_discover_calendars()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(self.account.url, 'https://dav.example.com/me/calendar/')
        self.assertEqual(self.account.sync_status, 'active')
