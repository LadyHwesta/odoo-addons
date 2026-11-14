# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTelehealthCourse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref("telehealth_booking_elearning.channel_telehealth")

    def test_published_for_every_employee(self):
        self.assertTrue(self.channel.is_published)
        self.assertIn(self.env.ref("base.group_user"), self.channel.enroll_group_ids)

    def test_structure(self):
        self.assertEqual(len(self.channel.slide_ids.filtered("is_category")), 2)
        lessons = self.channel.slide_content_ids.filtered(lambda s: s.slide_category == "article")
        self.assertEqual(len(lessons), 4)

    def test_quiz_answers_are_valid(self):
        quiz = self.channel.slide_content_ids.filtered(lambda s: s.slide_category == "quiz")
        self.assertEqual(len(quiz.question_ids), 3)
        for question in quiz.question_ids:
            self.assertFalse(question.answers_validation_error)
            self.assertEqual(len(question.answer_ids.filtered("is_correct")), 1)

    def test_every_lesson_is_published(self):
        data = self.env["ir.model.data"].search(
            [("module", "=", "telehealth_booking_elearning"), ("model", "=", "slide.slide")])
        self.assertFalse(self.env["slide.slide"].browse(data.mapped("res_id")).filtered(
            lambda s: not s.is_published))

    def test_the_labels_it_teaches_are_real(self):
        tiers = dict(self.env["res.users"]._fields["telehealth_video_tier"].selection)
        self.assertEqual(tiers["basic"], "Basic (built-in)")
        self.assertEqual(tiers["premium"], "Premium")
        self.assertEqual(self.env["res.users"]._fields["telehealth_video_tier"].string,
                         "Telehealth Video Tier")
        form = self.env.ref("telehealth_booking.view_calendar_event_form_inherit_telehealth").arch
        self.assertIn("Get Telehealth Video Link", form)

    def test_no_vendor_names(self):
        """Customers see this course: no supplier names (white label)."""
        text = " ".join(self.channel.slide_ids.mapped("html_content") + [self.channel.description])
        self.assertNotIn("SignalWire", text)
