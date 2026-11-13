# -*- coding: utf-8 -*-
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path


@tagged("post_install", "-at_install")
class TestElearningTeamFolder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref("dms_elearning_team_folder.channel_team_folders")

    def test_course_is_published_and_gated(self):
        self.assertTrue(self.channel.is_published)
        self.assertEqual(self.channel.visibility, "members")
        self.assertIn(self.env.ref("dms.group_dms_user"), self.channel.enroll_group_ids)

    def test_course_structure(self):
        self.assertEqual(len(self.channel.slide_ids.filtered("is_category")), 7)
        lessons = self.channel.slide_content_ids.filtered(
            lambda s: s.slide_category == "article")
        self.assertEqual(len(lessons), 12)
        for lesson in lessons:
            self.assertTrue(lesson.category_id, "%s has no section" % lesson.name)

    def test_quiz_answers_are_valid(self):
        quiz = self.channel.slide_content_ids.filtered(
            lambda s: s.slide_category == "quiz")
        self.assertEqual(len(quiz.question_ids), 5)
        for question in quiz.question_ids:
            self.assertFalse(question.answers_validation_error)
            self.assertEqual(len(question.answer_ids.filtered("is_correct")), 1)

    def test_screenshots_exist(self):
        found = []
        for lesson in self.channel.slide_content_ids:
            found += re.findall(r'src="/([^"]+\.png)"', lesson.html_content or "")
        self.assertEqual(len(found), 5)
        for image in found:
            self.assertTrue(file_path(image))

    def test_every_lesson_is_published(self):
        """A lesson starts unpublished, so each one must say so in the data,
        or learners see the course but none of its pages."""
        data = self.env["ir.model.data"].search(
            [("module", "=", "dms_elearning_team_folder"), ("model", "=", "slide.slide")])
        lessons = self.env["slide.slide"].browse(data.mapped("res_id"))
        self.assertTrue(lessons)
        self.assertFalse(lessons.filtered(lambda s: not s.is_published).mapped("name"))
