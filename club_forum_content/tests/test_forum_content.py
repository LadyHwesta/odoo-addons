# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged

# 110 questions ported from the old bbPress forum (128 slugs in the
# sitemap, 18 already 404 on the live site and were skipped), 133
# replies - kept as constants so a miscount shows up immediately
# rather than needing separate lookups.
EXPECTED_QUESTIONS = 110
EXPECTED_REPLIES = 133
EXPECTED_BY_FORUM = {
    "Activities": 38,
    "Announcements and News": 78,
    "Technical Questions and Answers": 127,
}


@tagged("post_install", "-at_install")
class TestClubForumContent(HttpCase):

    def test_import_user_exists(self):
        user = self.env["res.users"].with_context(active_test=False).search(
            [("login", "=", "forum-archive-import")])
        self.assertTrue(user, "the Forum Archive Import user should exist")
        self.assertFalse(user.active,
                          "the import user should be inactive - it's not a real login")

    def test_post_and_reply_counts(self):
        questions = self.env["forum.post"].search([("parent_id", "=", False),
                                                     ("create_uid", "=", self._import_user_id())])
        replies = self.env["forum.post"].search([("parent_id", "!=", False),
                                                   ("create_uid", "=", self._import_user_id())])
        self.assertEqual(len(questions), EXPECTED_QUESTIONS,
                          "expected %d ported questions" % EXPECTED_QUESTIONS)
        self.assertEqual(len(replies), EXPECTED_REPLIES,
                          "expected %d ported replies" % EXPECTED_REPLIES)

    def test_categories_and_post_distribution(self):
        forums = self.env["forum.forum"].search([("name", "in", list(EXPECTED_BY_FORUM))])
        self.assertEqual(len(forums), 3, "expected all 3 ported forum categories")
        for forum in forums:
            count = self.env["forum.post"].search_count([("forum_id", "=", forum.id)])
            self.assertEqual(count, EXPECTED_BY_FORUM[forum.name],
                              "unexpected post count in %s" % forum.name)

    def test_replies_are_threaded_to_a_question_in_the_same_forum(self):
        replies = self.env["forum.post"].search([("parent_id", "!=", False),
                                                   ("create_uid", "=", self._import_user_id())])
        for reply in replies:
            with self.subTest(reply=reply.name, id=reply.id):
                self.assertFalse(reply.parent_id.parent_id,
                                  "a reply's parent should be a top-level question")
                self.assertEqual(reply.forum_id, reply.parent_id.forum_id,
                                  "a reply should live in the same forum as its question")

    def test_forum_index_pages_load_200(self):
        for name in EXPECTED_BY_FORUM:
            forum = self.env["forum.forum"].search([("name", "=", name)], limit=1)
            with self.subTest(forum=name):
                resp = self.url_open(forum._compute_website_url())
                self.assertEqual(resp.status_code, 200,
                                  "%s forum page did not return 200" % name)

    def _import_user_id(self):
        return self.env["res.users"].with_context(active_test=False).search(
            [("login", "=", "forum-archive-import")]).id
