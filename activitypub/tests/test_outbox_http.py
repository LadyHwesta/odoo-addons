# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestOutboxHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        cls.website.domain = ''
        cls.env['ir.config_parameter'].sudo().set_param('activitypub.enabled', 'True')
        cls.actor = cls.env['activitypub.actor'].create({
            'website_id': cls.website.id,
            'actor_type': 'Service',
            'username': 'news',
            'name': 'News',
        })
        cls.env['activitypub.follower'].create({
            'actor_id': cls.actor.id,
            'follower_uri': 'https://remote.example/users/bob',
            'shared_inbox_url': 'https://remote.example/inbox',
            'state': 'accepted',
        })
        partner = cls.env.user.partner_id
        cls.actor._ap_publish('res.partner', partner.id, 'Note', {'content': 'one'})
        cls.actor._ap_publish('res.partner', cls.env.ref('base.partner_admin').id,
                              'Note', {'content': 'two'})

    def _get(self, url, accept='application/activity+json'):
        return self.url_open(url, headers={'Accept': accept}, allow_redirects=False)

    def test_outbox_collection_summary(self):
        r = self._get(f'/ap/actors/{self.actor.id}/outbox')
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertEqual(doc['type'], 'OrderedCollection')
        self.assertEqual(doc['totalItems'], 2)
        self.assertIn('page=1', doc['first'])

    def test_outbox_page_lists_activities(self):
        r = self._get(f'/ap/actors/{self.actor.id}/outbox?page=1')
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertEqual(doc['type'], 'OrderedCollectionPage')
        self.assertEqual(len(doc['orderedItems']), 2)
        self.assertTrue(all(i['type'] == 'Create' for i in doc['orderedItems']))
        self.assertEqual(doc['orderedItems'][0]['object']['type'], 'Note')

    def test_followers_collection_counts(self):
        r = self._get(f'/ap/actors/{self.actor.id}/followers')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['totalItems'], 1)

    def test_object_served_and_negotiated(self):
        obj = self.env['activitypub.object'].search(
            [('actor_id', '=', self.actor.id)], limit=1)
        r = self._get(f'/ap/objects/{obj.id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['id'], obj.uri)
        r2 = self._get(f'/ap/objects/{obj.id}', accept='text/html')
        self.assertIn(r2.status_code, (302, 303))

    def test_activity_served_as_json(self):
        act = self.env['activitypub.activity'].search(
            [('actor_id', '=', self.actor.id), ('direction', '=', 'out')], limit=1)
        r = self._get(f'/ap/activities/{act.id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['id'], act.uri)
