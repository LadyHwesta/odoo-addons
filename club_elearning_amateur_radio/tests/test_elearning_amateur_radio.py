# -*- coding: utf-8 -*-
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path


@tagged("post_install", "-at_install")
class TestElearningAmateurRadio(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref(
            "club_elearning_amateur_radio.channel_amateur_radio")

    def test_course_is_published_and_gated(self):
        self.assertTrue(self.channel.is_published)
        self.assertEqual(self.channel.visibility, "members")
        self.assertIn(
            self.env.ref("membership.group_membership_manager"),
            self.channel.enroll_group_ids)

    def test_course_structure(self):
        sections = self.channel.slide_ids.filtered("is_category")
        self.assertEqual(len(sections), 2)
        lessons = self.channel.slide_content_ids.filtered(
            lambda s: s.slide_category == "article")
        self.assertEqual(len(lessons), 3)
        for lesson in lessons:
            self.assertTrue(lesson.category_id, "%s has no section" % lesson.name)

    def test_quiz_answers_are_valid(self):
        quiz = self.channel.slide_content_ids.filtered(
            lambda s: s.slide_category == "quiz")
        self.assertEqual(len(quiz), 1)
        self.assertEqual(len(quiz.question_ids), 4)
        for question in quiz.question_ids:
            self.assertFalse(question.answers_validation_error)
            self.assertEqual(
                len(question.answer_ids.filtered("is_correct")), 1)

    def test_screenshots_exist(self):
        found = []
        for channel in (self.channel,):
            for lesson in channel.slide_content_ids:
                found += re.findall(r'src="/([^"]+\.png)"', lesson.html_content or "")
        self.assertTrue(found)
        for image in found:
            self.assertTrue(file_path(image))

    def test_every_lesson_is_published(self):
        """A lesson starts unpublished, so each one must say so in the data,
        or learners see the course but none of its pages."""
        data = self.env["ir.model.data"].search(
            [("module", "=", "club_elearning_amateur_radio"), ("model", "=", "slide.slide")])
        lessons = self.env["slide.slide"].browse(data.mapped("res_id"))
        self.assertTrue(lessons)
        self.assertFalse(lessons.filtered(lambda s: not s.is_published).mapped("name"))
