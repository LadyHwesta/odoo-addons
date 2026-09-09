# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEventVolunteer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create({
            "name": "Field Day",
            "date_begin": datetime.now() + timedelta(days=5),
            "date_end": datetime.now() + timedelta(days=6),
        })
        cls.role = cls.env["event.volunteer.role"].create({
            "event_id": cls.event.id,
            "name": "Net Control",
            "slot_count": 2,
        })
        cls.p1 = cls.env["res.partner"].create({"name": "Ann", "email": "ann@test.com"})
        cls.p2 = cls.env["res.partner"].create({"name": "Bo", "email": "bo@test.com"})
        cls.p3 = cls.env["res.partner"].create({"name": "Cy", "email": "cy@test.com"})

    def _assign(self, partner, **kw):
        return self.env["event.volunteer.assignment"].create(dict({
            "role_id": self.role.id,
            "partner_id": partner.id,
        }, **kw))

    # ------------------------------------------------------------------
    def test_role_counts_and_fill_state(self):
        self.assertEqual(self.role.fill_state, "empty")
        a1 = self._assign(self.p1)
        self.assertEqual(self.role.filled_count, 1)
        self.assertEqual(self.role.seats_available, 1)
        self.assertEqual(self.role.fill_state, "partial")
        self._assign(self.p2)
        self.assertEqual(self.role.fill_state, "full")
        self.assertEqual(self.role.seats_available, 0)
        a1.action_portal_withdraw()
        self.assertEqual(self.role.filled_count, 1)
        self.assertEqual(self.role.fill_state, "partial")

    def test_capacity_blocks_third_backoffice_signup(self):
        self._assign(self.p1)
        self._assign(self.p2)
        with self.assertRaises(ValidationError):
            self._assign(self.p3)

    def test_capacity_can_be_forced_with_context(self):
        self._assign(self.p1)
        self._assign(self.p2)
        forced = self.env["event.volunteer.assignment"].with_context(
            skip_volunteer_capacity=True).create({
                "role_id": self.role.id, "partner_id": self.p3.id})
        self.assertEqual(forced.role_id.fill_state, "over")

    def test_no_duplicate_active_signup(self):
        self._assign(self.p1)
        with self.assertRaises(ValidationError):
            self._assign(self.p1)

    def test_portal_volunteer_and_withdraw(self):
        a = self.role.action_portal_volunteer(self.p1)
        self.assertEqual(a.state, "confirmed")
        self.assertEqual(a.source, "portal")
        with self.assertRaises(UserError):
            self.role.action_portal_volunteer(self.p1)  # already on it
        a.action_portal_withdraw()
        self.assertEqual(a.state, "cancelled")
        # a freed seat can be taken again
        a2 = self.role.action_portal_volunteer(self.p1)
        self.assertNotEqual(a2, a)
        self.assertEqual(self.role.filled_count, 1)

    def test_portal_volunteer_refused_when_full(self):
        self.role.action_portal_volunteer(self.p1)
        self.role.action_portal_volunteer(self.p2)
        with self.assertRaises(UserError):
            self.role.action_portal_volunteer(self.p3)

    def test_signup_sends_confirmation_mail(self):
        a = self._assign(self.p1)
        mails = self.env["mail.mail"].search([
            ("model", "=", "event.volunteer.assignment"),
            ("res_id", "=", a.id),
        ])
        self.assertTrue(mails, "a confirmation email is queued on sign-up")

    def test_reminder_cron(self):
        # setUpClass event begins in 5 days; use a 7-day lead so it's inside
        # the window and the 40-day-out event below is still outside it.
        self.env["ir.config_parameter"].sudo().set_param(
            "event_volunteer.reminder_lead_days", "7")
        soon = self._assign(self.p1)
        far_event = self.env["event.event"].create({
            "name": "Winter Field Day",
            "date_begin": datetime.now() + timedelta(days=40),
            "date_end": datetime.now() + timedelta(days=41),
        })
        far_role = self.env["event.volunteer.role"].create({
            "event_id": far_event.id, "name": "Logger", "slot_count": 5})
        far = self.env["event.volunteer.assignment"].create({
            "role_id": far_role.id, "partner_id": self.p1.id})

        self.env["event.volunteer.assignment"]._cron_send_volunteer_reminders()
        soon.invalidate_recordset()
        far.invalidate_recordset()
        self.assertTrue(soon.reminder_sent, "event within lead window -> reminded")
        self.assertFalse(far.reminder_sent, "event beyond lead window -> not yet")

        # second run doesn't re-send
        mails_before = self.env["mail.mail"].search_count([
            ("model", "=", "event.volunteer.assignment"), ("res_id", "=", soon.id)])
        self.env["event.volunteer.assignment"]._cron_send_volunteer_reminders()
        mails_after = self.env["mail.mail"].search_count([
            ("model", "=", "event.volunteer.assignment"), ("res_id", "=", soon.id)])
        self.assertEqual(mails_before, mails_after)

    def test_event_rollup_stats(self):
        self.env["event.volunteer.role"].create({
            "event_id": self.event.id, "name": "Setup Crew", "slot_count": 4})
        self._assign(self.p1)
        self.event.invalidate_recordset()
        self.assertEqual(self.event.volunteer_slot_count, 6)
        self.assertEqual(self.event.volunteer_filled_count, 1)
        self.assertTrue(self.event.volunteer_understaffed)

    def test_roles_copied_when_event_duplicated(self):
        self._assign(self.p1)
        copy = self.event.copy()
        self.assertEqual(len(copy.volunteer_role_ids), 1)
        self.assertEqual(copy.volunteer_role_ids.name, "Net Control")
        self.assertFalse(
            copy.volunteer_role_ids.assignment_ids,
            "a duplicated event starts with an empty roster")


@tagged("post_install", "-at_install")
class TestEventVolunteerPortal(HttpCase):
    def test_event_page_renders_volunteer_section_for_public(self):
        event = self.env["event.event"].create({
            "name": "Open House",
            "date_begin": datetime.now() + timedelta(days=7),
            "date_end": datetime.now() + timedelta(days=7, hours=3),
            "website_published": True,
        })
        self.env["event.volunteer.role"].create({
            "event_id": event.id, "name": "Greeter", "slot_count": 3})
        # public (not logged in) must not hit an AccessError on the roster
        resp = self.url_open("/event/%s" % event.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Greeter", resp.text)
        self.assertIn("Sign in", resp.text)
