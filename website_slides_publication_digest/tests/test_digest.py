# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged

SUBTYPE = 'website_slides.mt_channel_slide_published'


@tagged('post_install', '-at_install')
class TestPublicationDigest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.channel = cls.env['slide.channel'].create({'name': 'Logging Your Time', 'is_published': True})
        cls.subtype = cls.env.ref(SUBTYPE)

    def _announcements(self):
        return self.channel.message_ids.filtered(lambda m: m.subtype_id == self.subtype)

    def _lesson(self, name, published=True, **ctx):
        return self.env['slide.slide'].with_context(**ctx).create({
            'name': name, 'channel_id': self.channel.id, 'slide_category': 'article',
            'html_content': '<p>x</p>', 'is_published': published})

    def test_publishing_by_hand_still_announces_once(self):
        lesson = self._lesson('Start work', published=False)
        lesson.is_published = True
        self.assertEqual(len(self._announcements()), 1)
        lesson.write({'is_published': True, 'name': 'Start work and stop work'})
        self.assertEqual(len(self._announcements()), 1)

    def test_module_updates_send_one_digest_per_course(self):
        lessons = self._lesson('One', install_mode=True) | self._lesson('Two', install_mode=True) \
            | self._lesson('Three', install_mode=True)
        # An update re-saving published lessons queues nothing more.
        lessons.with_context(install_mode=True).write({'is_published': True})
        self.assertFalse(self._announcements())
        # Only this course's queue: course modules installed alongside may
        # have left their own lessons waiting for the digest.
        self.assertEqual(len(self.env['slide.publication.queue'].search([('channel_id', '=', self.channel.id)])), 3)
        self.env['slide.slide']._cron_send_publication_digests()
        digest = self._announcements()
        self.assertEqual(len(digest), 1)
        self.assertEqual(digest.subject, '3 new in Logging Your Time')
        for name in ('One', 'Two', 'Three'):
            self.assertIn(name, digest.body)
        self.assertFalse(self.env['slide.publication.queue'].search([]))

    def test_unpublished_before_the_digest_is_left_out(self):
        first = self._lesson('Kept', install_mode=True)
        second = self._lesson('Withdrawn', install_mode=True)
        second.is_published = False
        self.env['slide.slide']._cron_send_publication_digests()
        self.assertEqual(self._announcements().subject, 'New in Logging Your Time: Kept')
        self.assertTrue(first)
