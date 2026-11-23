# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestPublicMeetingsCourse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env.ref("calendar_public_meeting_elearning.channel_public_meetings")

    def test_published_with_lessons_and_a_valid_quiz(self):
        self.assertTrue(self.channel.is_published)
        self.assertEqual(len(self.channel.slide_ids.filtered("is_category")), 2)
        self.assertEqual(len(self.channel.slide_content_ids.filtered(
            lambda s: s.slide_category == "article")), 4)
        quiz = self.channel.slide_content_ids.filtered(lambda s: s.slide_category == "quiz")
        for question in quiz.question_ids:
            self.assertFalse(question.answers_validation_error)
            self.assertEqual(len(question.answer_ids.filtered("is_correct")), 1)
        self.assertFalse(self.channel.slide_ids.filtered(lambda s: not s.is_published))

    def test_the_labels_it_teaches_are_real(self):
        event = self.env["calendar.event"]._fields
        self.assertEqual(event["public_meeting"].string, "Public Meeting")
        self.assertEqual(event["public_max_viewers"].string, "Viewer Limit")
        self.assertEqual(event["public_watch_url"].string, "Watch Link")
        pages = self.env.ref("calendar_public_meeting.watch_page").arch \
            + self.env.ref("calendar_public_meeting.join_page").arch \
            + self.env.ref("calendar_public_meeting.room_page").arch \
            + file_open("calendar_public_meeting/static/src/js/meeting_room.js").read()
        for label in ("Watch the meeting", "Join the meeting", "Start watching", "Mute",
                      "Stop Camera", "Share Screen", "Settings", "Panel", "Leave",
                      "Check your camera and sound", "Microphone on", "Camera on", "Chat",
                      "Questions", "Documents", "Add a document", "Show everyone",
                      "Take down", "Mark answered", "Ask a question"):
            self.assertIn(label, pages)

    def test_no_vendor_names(self):
        text = " ".join(h for h in self.channel.slide_ids.mapped("html_content") if h)
        self.assertNotIn("SignalWire", text)
