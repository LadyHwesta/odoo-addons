# -*- coding: utf-8 -*-
import json

from odoo.tests.common import HttpCase, tagged

# A 1x1 transparent PNG.
PNG_1PX = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8'
    'z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)


@tagged('post_install', '-at_install')
class TestActivityPubControllers(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        # The test HTTP server answers on 127.0.0.1; keep the website domain
        # empty so request.website resolves to this one and the actor URLs
        # fall back to web.base.url (which the HttpCase points at the test
        # server). We assert on paths, not on the host.
        cls.website.domain = ''
        cls.env['ir.config_parameter'].sudo().set_param('activitypub.enabled', 'True')
        cls.actor = cls.env['activitypub.actor'].create({
            'website_id': cls.website.id,
            'actor_type': 'Service',
            'username': 'news',
            'name': 'Example News',
        })

    def _get(self, url, accept):
        return self.url_open(url, headers={'Accept': accept}, allow_redirects=False)

    def test_webfinger_resolves_known_actor(self):
        host = self.actor.domain
        r = self._get(f'/.well-known/webfinger?resource=acct:news@{host}',
                      'application/jrd+json')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['subject'], f'acct:news@{host}')
        self_link = next(l for l in body['links'] if l['rel'] == 'self')
        self.assertEqual(self_link['href'], self.actor.actor_url)
        self.assertEqual(self_link['type'], 'application/activity+json')

    def test_webfinger_unknown_actor_404(self):
        r = self._get('/.well-known/webfinger?resource=acct:nobody@' + self.actor.domain,
                      'application/jrd+json')
        self.assertEqual(r.status_code, 404)

    def test_webfinger_bad_resource_400(self):
        r = self._get('/.well-known/webfinger?resource=https://x/y', 'application/jrd+json')
        self.assertEqual(r.status_code, 400)

    def test_actor_document_served_as_activitypub(self):
        r = self._get(f'/ap/actors/{self.actor.id}', 'application/activity+json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('activity+json', r.headers.get('Content-Type', ''))
        doc = r.json()
        self.assertEqual(doc['id'], self.actor.actor_url)
        self.assertEqual(doc['preferredUsername'], 'news')
        self.assertIn('publicKey', doc)

    def test_actor_url_redirects_browser(self):
        r = self._get(f'/ap/actors/{self.actor.id}', 'text/html')
        self.assertIn(r.status_code, (302, 303))

    def test_outbox_and_followers_empty_collections(self):
        for suffix in ('outbox', 'followers', 'following'):
            r = self._get(f'/ap/actors/{self.actor.id}/{suffix}',
                          'application/activity+json')
            self.assertEqual(r.status_code, 200, suffix)
            self.assertEqual(r.json()['totalItems'], 0, suffix)

    def test_nodeinfo_discovery(self):
        r = self._get('/.well-known/nodeinfo', 'application/json')
        self.assertEqual(r.status_code, 200)
        rel = r.json()['links'][0]['rel']
        self.assertIn('nodeinfo', rel)
        r2 = self._get('/nodeinfo/2.1', 'application/json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['software']['name'], 'odoo-activitypub')

    def test_disabled_federation_hides_endpoints(self):
        self.env['ir.config_parameter'].sudo().set_param('activitypub.enabled', 'False')
        try:
            r = self._get(f'/.well-known/webfinger?resource=acct:news@{self.actor.domain}',
                          'application/jrd+json')
            self.assertEqual(r.status_code, 404)
            r2 = self._get(f'/ap/actors/{self.actor.id}', 'application/activity+json')
            self.assertEqual(r2.status_code, 404)
        finally:
            self.env['ir.config_parameter'].sudo().set_param('activitypub.enabled', 'True')

    def test_inbox_rejects_malformed_activity(self):
        # No 'actor' and no signature: rejected before any processing.
        r = self.url_open(
            f'/ap/actors/{self.actor.id}/inbox',
            data=json.dumps({'type': 'Follow'}),
            headers={'Content-Type': 'application/activity+json'},
            allow_redirects=False,
        )
        self.assertEqual(r.status_code, 400)

    def test_inbox_rejects_non_json(self):
        r = self.url_open(
            f'/ap/actors/{self.actor.id}/inbox',
            data=b'not json',
            headers={'Content-Type': 'application/activity+json'},
            allow_redirects=False,
        )
        self.assertEqual(r.status_code, 400)

    def test_actor_icon_served_publicly(self):
        # No icon yet -> 404, and no icon key in the doc.
        self.assertEqual(self._get(f'/ap/actors/{self.actor.id}/icon', '*/*').status_code, 404)
        self.assertNotIn('icon', self._get(
            f'/ap/actors/{self.actor.id}', 'application/activity+json').json())

        self.actor.icon = PNG_1PX
        r = self._get(f'/ap/actors/{self.actor.id}/icon', '*/*')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('Content-Type'), 'image/png')
        self.assertTrue(r.content.startswith(b'\x89PNG'))

        doc = self._get(f'/ap/actors/{self.actor.id}', 'application/activity+json').json()
        self.assertEqual(doc['icon']['type'], 'Image')
        self.assertEqual(doc['icon']['mediaType'], 'image/png')
        self.assertTrue(doc['icon']['url'].endswith(f'/ap/actors/{self.actor.id}/icon'))
