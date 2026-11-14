# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOnlineBookingCourse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref("resource_booking_online_elearning.channel_online_booking")

    def test_published_with_lessons_and_a_valid_quiz(self):
        self.assertTrue(self.channel.is_published)
        self.assertEqual(len(self.channel.slide_ids.filtered("is_category")), 2)
        self.assertEqual(len(self.channel.slide_content_ids.filtered(
            lambda s: s.slide_category == "article")), 5)
        quiz = self.channel.slide_content_ids.filtered(lambda s: s.slide_category == "quiz")
        self.assertEqual(len(quiz.question_ids), 3)
        for question in quiz.question_ids:
            self.assertFalse(question.answers_validation_error)
            self.assertEqual(len(question.answer_ids.filtered("is_correct")), 1)
        self.assertFalse(self.channel.slide_ids.filtered(lambda s: not s.is_published))

    def test_the_labels_it_teaches_are_real(self):
        menus = set(self.env["ir.ui.menu"].search([]).mapped("name"))
        for name in ("Resource Bookings", "Bookings", "Types", "Combinations", "Configuration"):
            self.assertIn(name, menus)
        fields = self.env["resource.booking.type"]._fields
        self.assertEqual(fields["resource_calendar_id"].string, "Availability Calendar")
        self.assertEqual(fields["combination_rel_ids"].string, "Available resource combinations")
        for name, label in (("online_booking", "Bookable Online"), ("online_organizer_id", "Organizer"),
                            ("video_appointment", "Video Appointment"),
                            ("online_description", "Online Description")):
            self.assertEqual(fields[name].string, label)
        self.assertIn("Next: pick a time", self.env.ref("resource_booking_online.book_type").arch)
