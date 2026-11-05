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
        self.assertEqual(len(lessons), 11)
        for lesson in lessons:
            self.assertTrue(lesson.category_id, "%s has no section" % lesson.name)

    def test_quiz_answers_are_valid(self):
        quiz = self.channel.slide_content_ids.filtered(
            lambda s: s.slide_category == "quiz")
        self.assertEqual(len(quiz.question_ids), 4)
        for question in quiz.question_ids:
            self.assertFalse(question.answers_validation_error)
            self.assertEqual(len(question.answer_ids.filtered("is_correct")), 1)

    def test_screenshots_exist(self):
        found = []
        for lesson in self.channel.slide_content_ids:
            found += re.findall(r'src="/([^"]+\.png)"', lesson.html_content or "")
        self.assertEqual(len(found), 3)
        for image in found:
            self.assertTrue(file_path(image))
