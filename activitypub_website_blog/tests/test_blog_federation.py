# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

PUBLIC = 'https://www.w3.org/ns/activitystreams#Public'


@tagged('post_install', '-at_install')
class TestBlogFederation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        cls.website.domain = 'https://news.example.com'
        cls.actor = cls.env['activitypub.actor'].create({
            'website_id': cls.website.id,
            'actor_type': 'Group',
            'username': 'blog',
            'name': 'Company Blog',
        })
        cls.blog = cls.env['blog.blog'].create({
            'name': 'Company Blog',
            'website_id': cls.website.id,
            'activitypub_actor_id': cls.actor.id,
        })
        cls.env['activitypub.follower'].create({
            'actor_id': cls.actor.id,
            'follower_uri': 'https://remote.example/users/bob',
            'shared_inbox_url': 'https://remote.example/inbox',
            'state': 'accepted',
        })

    def _object(self, post):
        return self.env['activitypub.object'].search([
            ('source_model', '=', 'blog.post'),
            ('source_res_id', '=', post.id),
        ], limit=1)

    def _activities(self, post, activity_type=None):
        obj = self._object(post)
        domain = [('object_id', '=', obj.id)]
        if activity_type:
            domain.append(('activity_type', '=', activity_type))
        return self.env['activitypub.activity'].search(domain)

    def _publish(self, name, **vals):
        return self.env['blog.post'].create(dict({
            'name': name, 'blog_id': self.blog.id, 'website_published': True,
        }, **vals))

    # ------------------------------------------------------------------
    def test_publish_creates_note_and_queues_delivery(self):
        post = self._publish('Hello world')
        obj = self._object(post)
        self.assertTrue(obj)
        # Note, not Article: Mastodon's Create handler only materializes a
        # visible status for Note (confirmed against a real instance -
        # Article is accepted and counted but never shown).
        self.assertEqual(obj.object_type, 'Note')
        self.assertEqual(obj.payload['type'], 'Note')
        self.assertEqual(obj.payload['attributedTo'], self.actor.actor_url)
        self.assertEqual(obj.payload['to'], [PUBLIC])
        self.assertEqual(obj.payload['name'], 'Hello world')
        # The title (as a Note has none Mastodon displays) is linked into
        # the body, and `summary` is never used - Mastodon reads it as a
        # content warning, which would hide the post.
        self.assertIn('Hello world', obj.payload['content'])
        self.assertNotIn('summary', obj.payload)
        self.assertTrue(obj.payload['url'].startswith('https://news.example.com/'))

        create = self._activities(post, 'Create')
        self.assertEqual(len(create), 1)
        self.assertEqual(create.payload['type'], 'Create')
        self.assertEqual(create.delivery_ids.inbox_url, 'https://remote.example/inbox')
        self.assertTrue(self.actor.federated_once)

    def test_subtitle_is_folded_into_content_not_summary(self):
        post = self._publish('Titled', subtitle='A subtitle')
        obj = self._object(post)
        self.assertNotIn('summary', obj.payload)
        self.assertIn('A subtitle', obj.payload['content'])

    def test_body_uses_plain_text_teaser_not_raw_builder_html(self):
        # self.content is raw website-builder markup (snippet divs,
        # data-oe-*/data-snippet attributes) - it must never be embedded
        # as-is; only the plain-text teaser Odoo derives from it should
        # reach the federated body.
        post = self._publish('Deep dive', content=(
            '<section class="s_text_block" data-snippet="s_text_block">'
            '<div class="container"><p>Some real prose here.</p></div>'
            '</section>'
        ))
        content = self._object(post).payload['content']
        self.assertNotIn('data-snippet', content)
        self.assertNotIn('s_text_block', content)
        self.assertNotIn('<section', content)
        self.assertIn('Some real prose here.', content)
        self.assertIn('Continue reading', content)

    def test_edit_published_post_sends_update(self):
        post = self._publish('First title')
        post.write({'name': 'Second title'})
        self.assertTrue(self._activities(post, 'Update'))
        self.assertEqual(self._object(post).payload['name'], 'Second title')

    def test_unpublish_sends_delete_and_tombstones(self):
        post = self._publish('To be pulled')
        post.write({'website_published': False})
        self.assertTrue(self._activities(post, 'Delete'))
        self.assertTrue(self._object(post).deleted)

    def test_republish_after_unpublish_mints_a_new_object_uri(self):
        # Once a Delete/Tombstone has gone out for a URI, compliant servers
        # permanently refuse to resurrect a Create for that same id
        # (confirmed against Mastodon's own source: it rejects a Create
        # outright when a Tombstone already exists for the object URI).
        # Re-publishing must get a brand new object/URI, not reuse the one
        # already tombstoned.
        post = self._publish('Comeback')
        old_obj = self._object(post)
        post.write({'website_published': False})
        self.assertTrue(old_obj.deleted)

        post.write({'website_published': True})
        new_obj = self._object(post)
        self.assertNotEqual(new_obj.id, old_obj.id)
        self.assertNotEqual(new_obj.uri, old_obj.uri)
        self.assertFalse(new_obj.deleted)

        create = self._activities(post, 'Create')
        self.assertEqual(len(create), 1)
        self.assertEqual(create.object_id, new_obj)

    def test_delete_post_sends_delete(self):
        post = self._publish('Doomed')
        obj = self._object(post)
        post.unlink()
        self.assertTrue(self.env['activitypub.activity'].search([
            ('object_id', '=', obj.id), ('activity_type', '=', 'Delete')]))

    def test_unpublished_post_does_not_federate(self):
        post = self.env['blog.post'].create({
            'name': 'Draft', 'blog_id': self.blog.id, 'website_published': False})
        self.assertFalse(self._object(post))

    def test_blog_without_actor_does_not_federate(self):
        other_blog = self.env['blog.blog'].create({
            'name': 'Unwired', 'website_id': self.website.id})
        post = self.env['blog.post'].create({
            'name': 'Nope', 'blog_id': other_blog.id, 'website_published': True})
        self.assertFalse(self._object(post))

    def test_author_actor_takes_precedence_over_blog(self):
        user = self.env['res.users'].create({
            'name': 'Wilma', 'login': 'wilma@example.com',
            'email': 'wilma@example.com',
        })
        author_actor = self.env['activitypub.actor'].create({
            'website_id': self.website.id,
            'actor_type': 'Person',
            'username': 'wilma',
            'name': 'Wilma',
            'user_id': user.id,
        })
        post = self._publish('By Wilma', author_id=user.partner_id.id)
        self.assertEqual(self._object(post).payload['attributedTo'],
                         author_actor.actor_url)

    def test_catch_up_federates_post_once_actor_configured_late(self):
        # Setting the actor is a write() on blog.blog, not on the post - it
        # never triggers the post's own _ap_sync(). This is exactly the
        # "published, but never federated because the actor wasn't set yet"
        # trap; the catch-up cron is the fix.
        unwired = self.env['blog.blog'].create({
            'name': 'Was Unwired', 'website_id': self.website.id})
        post = self.env['blog.post'].create({
            'name': 'Waiting', 'blog_id': unwired.id, 'website_published': True})
        self.assertFalse(self._object(post))

        unwired.activitypub_actor_id = self.actor.id
        self.assertFalse(self._object(post), "setting the actor alone must "
                                             "not have federated it yet")

        self.env['blog.post']._cron_federate_catch_up()
        obj = self._object(post)
        self.assertTrue(obj)
        self.assertTrue(self._activities(post, 'Create'))

    def test_catch_up_federates_post_whose_schedule_elapsed(self):
        post = self._publish(
            'Scheduled', post_date=fields.Datetime.now() + timedelta(hours=1))
        self.assertFalse(self._object(post), "future post_date: not public yet")

        # Simulate the scheduled date elapsing with nothing else touching
        # the post in the meantime (activitypub_no_sync stands in for "no
        # write ever reached _ap_sync", which is exactly the real gap).
        post.with_context(activitypub_no_sync=True).write({
            'post_date': fields.Datetime.now() - timedelta(minutes=1)})
        self.assertFalse(self._object(post))

        self.env['blog.post']._cron_federate_catch_up()
        self.assertTrue(self._object(post))
        self.assertTrue(self._activities(post, 'Create'))

    def test_catch_up_does_not_touch_already_federated_posts(self):
        post = self._publish('Already out')
        first_activity = self._activities(post, 'Create')
        self.assertEqual(len(first_activity), 1)

        self.env['blog.post']._cron_federate_catch_up()
        self.assertEqual(self._activities(post, 'Create'), first_activity,
                         "an already-federated post must not be re-published")
