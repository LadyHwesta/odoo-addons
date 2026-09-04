# -*- coding: utf-8 -*-
from unittest.mock import Mock, patch

from odoo.tests.common import TransactionCase, tagged

from ..models.caldav_service import _is_invalid_sync_token_error


@tagged('post_install', '-at_install')
class TestSyncTokenErrorClassification(TransactionCase):
    """Bug: every 403 on a sync-collection REPORT was treated as an invalid
    sync token (-> silently do a full resync), even a genuine auth failure
    that happens to answer with 403 - masking real credential problems.
    RFC 6578 Sec 3.2 says an invalid token specifically carries a
    DAV:valid-sync-token precondition in the error body, so that's what
    tells the two apart.
    """

    @staticmethod
    def _response(body):
        resp = Mock()
        resp.content = body.encode('utf-8')
        return resp

    def test_valid_sync_token_precondition_is_recognized(self):
        body = ('<?xml version="1.0"?>'
                '<D:error xmlns:D="DAV:"><D:valid-sync-token/></D:error>')
        self.assertTrue(_is_invalid_sync_token_error(self._response(body)))

    def test_precondition_is_recognized_under_any_namespace_prefix(self):
        # Some servers bind DAV: as the default namespace instead of `D`/`d`.
        body = '<?xml version="1.0"?><error xmlns="DAV:"><valid-sync-token/></error>'
        self.assertTrue(_is_invalid_sync_token_error(self._response(body)))

    def test_genuine_auth_failure_body_is_not_mistaken_for_it(self):
        body = '<?xml version="1.0"?><D:error xmlns:D="DAV:"><D:not-authenticated/></D:error>'
        self.assertFalse(_is_invalid_sync_token_error(self._response(body)))

    def test_unparseable_body_is_not_mistaken_for_it(self):
        self.assertFalse(_is_invalid_sync_token_error(self._response('not xml at all')))


@tagged('post_install', '-at_install')
class TestReadOnlyConflictIsLogged(TransactionCase):
    """Bug: a read-only account's events never had `need_caldav_sync` set
    (excluded on purpose, since read-only accounts never push) - but that
    same field doubles as the "edited locally since the last pull" signal
    _caldav_apply_remote_event() uses to log a conflict before an incoming
    remote version overwrites it. Excluding read-only accounts from the
    flag also silently defeated that logging for them, with no trace left
    that a local edit was ever lost.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = cls.env['caldav.account'].create({
            'user_id': cls.env.user.id,
            'name': 'Read-only feed',
            'url': 'https://caldav.example/cal/',
            'read_only': True,
        })

    def _make_event(self):
        # caldav_no_sync=True: mirrors how a pulled event is actually
        # created (_caldav_apply_remote_event), so it starts life already
        # "clean" - a plain create() here would itself set need_caldav_sync
        # (same as it always has for a writable account), which is exactly
        # the state a genuine local edit afterwards needs to be told apart
        # from. Re-browsed afterwards on a plain env: create() returns a
        # recordset still carrying that same context, and a subsequent
        # write() through it would inherit caldav_no_sync too and skip
        # dirty-flagging - not what a real local edit looks like.
        event = self.env['calendar.event'].with_context(caldav_no_sync=True).create({
            'name': 'Team offsite',
            'start': '2026-06-01 10:00:00',
            'stop': '2026-06-01 11:00:00',
            'caldav_account_id': self.account.id,
            'caldav_href': 'https://caldav.example/cal/offsite.ics',
        })
        return self.env['calendar.event'].browse(event.id)

    def test_local_edit_to_read_only_event_is_still_flagged(self):
        event = self._make_event()
        self.assertFalse(event.need_caldav_sync)
        event.write({'name': 'Team offsite (moved room)'})
        self.assertTrue(
            event.need_caldav_sync,
            "a local edit must be flagged even though it will never be "
            "pushed, so the next pull can detect and log the conflict "
            "instead of overwriting it without a trace")

    def test_conflicting_pull_logs_a_warning_before_overwriting(self):
        event = self._make_event()
        event.write({'name': 'Team offsite (moved room)'})
        item = {
            'href': 'https://caldav.example/cal/offsite.ics',
            'etag': '"remote-2"',
            'ics': (
                'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:offsite@remote\r\n'
                'SUMMARY:Team offsite\r\nDTSTART:20260601T100000Z\r\n'
                'DTEND:20260601T110000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
            ),
        }
        with self.assertLogs(
            'odoo.addons.caldav_calendar.models.caldav_account', level='WARNING',
        ) as cm:
            self.account._caldav_apply_remote_event(item)
        self.assertTrue(any('overwrites it' in msg for msg in cm.output))
        # Still remote-wins: the log makes the loss visible, it doesn't
        # change the (documented, intentional) outcome for a read-only feed.
        self.assertEqual(event.name, 'Team offsite')


@tagged('post_install', '-at_install')
class TestApplyRruleRollsBackOnFailure(TransactionCase):
    """Bug: `_caldav_apply_rrule` wrote the new `rrule` text onto the
    recurrence before expanding it into occurrence rows; if that expansion
    then raised, the exception was swallowed but the write had already
    landed, leaving the stored rule and the actual occurrences describing
    two different patterns.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = cls.env['caldav.account'].create({
            'user_id': cls.env.user.id,
            'name': 'Two-way calendar',
            'url': 'https://caldav.example/cal/',
            'username': 'bob',
            'password': 'secret',
        })

    def _make_master(self):
        return self.env['calendar.event'].create({
            'name': 'Standup',
            'start': '2026-06-01 09:00:00',
            'stop': '2026-06-01 09:15:00',
            'caldav_account_id': self.account.id,
            'caldav_href': 'https://caldav.example/cal/standup.ics',
        })

    def test_first_application_creates_a_working_series(self):
        event = self._make_master()
        self.account._caldav_apply_rrule(event, 'FREQ=DAILY;COUNT=3')
        self.assertTrue(event.recurrence_id)
        self.assertEqual(event.recurrence_id.rrule, 'FREQ=DAILY;COUNT=3')
        self.assertEqual(len(event.recurrence_id.calendar_event_ids), 3)

    def test_failed_change_rolls_back_rrule_and_occurrences(self):
        event = self._make_master()
        self.account._caldav_apply_rrule(event, 'FREQ=DAILY;COUNT=3')
        recurrence = event.recurrence_id
        occurrences_before = len(recurrence.calendar_event_ids)

        with patch.object(type(recurrence), '_apply_recurrence', side_effect=RuntimeError('boom')):
            self.account._caldav_apply_rrule(event, 'FREQ=WEEKLY;COUNT=5')

        recurrence.invalidate_recordset()
        self.assertEqual(
            recurrence.rrule, 'FREQ=DAILY;COUNT=3',
            "a failed expansion must not leave the stored rule pointing at "
            "a pattern the occurrences were never actually reconciled to")
        self.assertEqual(len(recurrence.calendar_event_ids), occurrences_before)

    def test_failed_new_recurrence_leaves_no_orphaned_recurrence(self):
        event = self._make_master()
        with patch.object(type(event), '_apply_recurrence_values', side_effect=RuntimeError('boom')):
            self.account._caldav_apply_rrule(event, 'FREQ=DAILY;COUNT=3')
        event.invalidate_recordset()
        self.assertFalse(event.recurrence_id)

    def test_unchanged_rule_is_a_no_op(self):
        event = self._make_master()
        self.account._caldav_apply_rrule(event, 'FREQ=DAILY;COUNT=3')
        with patch.object(type(event.recurrence_id), '_apply_recurrence') as mocked:
            self.account._caldav_apply_rrule(event, 'FREQ=DAILY;COUNT=3')
        mocked.assert_not_called()
