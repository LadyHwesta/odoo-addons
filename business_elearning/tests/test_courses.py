# -*- coding: utf-8 -*-
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools import file_path

MODULE = "business_elearning"
COURSES = {'channel_sales': (2, 3, 'base.group_user'), 'channel_work': (2, 4, 'base.group_user')}  # xmlid: (sections, article lessons, enrolled group)


@tagged("post_install", "-at_install")
class TestCourses(TransactionCase):

    def test_courses_are_built(self):
        for xmlid, (sections, lessons, group) in COURSES.items():
            with self.subTest(course=xmlid):
                channel = self.env.ref(f"{MODULE}.{xmlid}")
                self.assertTrue(channel.is_published)
                self.assertEqual((channel.visibility, channel.enroll), ("members", "invite"))
                self.assertIn(self.env.ref(group), channel.enroll_group_ids)
                self.assertEqual(len(channel.slide_ids.filtered("is_category")), sections)
                articles = channel.slide_content_ids.filtered(lambda s: s.slide_category == "article")
                self.assertEqual(len(articles), lessons)
                for lesson in articles:
                    self.assertTrue(lesson.category_id, f"{lesson.name} has no section")
                quiz = channel.slide_content_ids.filtered(lambda s: s.slide_category == "quiz")
                self.assertEqual(len(quiz.question_ids), 4)
                for question in quiz.question_ids:
                    self.assertFalse(question.answers_validation_error)
                    self.assertEqual(len(question.answer_ids.filtered("is_correct")), 1)

    def test_every_lesson_is_published(self):
        data = self.env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "slide.slide")])
        lessons = self.env["slide.slide"].browse(data.mapped("res_id"))
        self.assertTrue(lessons)
        self.assertFalse(lessons.filtered(lambda s: not s.is_published).mapped("name"))

    def test_screenshots_exist(self):
        found = []
        for xmlid in COURSES:
            for lesson in self.env.ref(f"{MODULE}.{xmlid}").slide_content_ids:
                found += re.findall(r'src="/([^"]+\.png)"', lesson.html_content or "")
        self.assertTrue(found)
        for image in found:
            self.assertTrue(file_path(image), image)
