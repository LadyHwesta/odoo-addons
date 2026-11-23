# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVideoMeetingsCourse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref("elearning_video_meetings.channel_video_meetings")

    def test_published_for_every_employee(self):
        self.assertTrue(self.channel.is_published)
        self.assertIn(self.env.ref("base.group_user"), self.channel.enroll_group_ids)

    def test_structure(self):
        self.assertEqual(len(self.channel.slide_ids.filtered("is_category")), 2)
        lessons = self.channel.slide_content_ids.filtered(lambda s: s.slide_category == "article")
        self.assertEqual(len(lessons), 5)
        for lesson in lessons:
            self.assertTrue(lesson.category_id, "%s has no section" % lesson.name)

    def test_quiz_answers_are_valid(self):
        quiz = self.channel.slide_content_ids.filtered(lambda s: s.slide_category == "quiz")
        self.assertEqual(len(quiz.question_ids), 4)
        for question in quiz.question_ids:
            self.assertFalse(question.answers_validation_error)
            self.assertEqual(len(question.answer_ids.filtered("is_correct")), 1)

    def test_every_lesson_is_published(self):
        data = self.env["ir.model.data"].search(
            [("module", "=", "elearning_video_meetings"), ("model", "=", "slide.slide")])
        self.assertFalse(self.env["slide.slide"].browse(data.mapped("res_id")).filtered(
            lambda s: not s.is_published))

    def test_the_labels_it_teaches_are_real(self):
        """Buttons and fields the lessons name, as the screens show them."""
        event = self.env["calendar.event"]
        self.assertEqual(event._fields["documents_in_invitations"].string,
                         "Send Documents with Invitations")
        self.assertEqual(self.env["ir.attachment"]._fields["meeting_private"].string, "Private")
        form = self.env.ref("calendar.view_calendar_event_form").arch
        self.assertIn('string="Video Link"', form)
        self.assertIn("Odoo meeting", form)
