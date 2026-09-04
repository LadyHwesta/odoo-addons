# -*- coding: utf-8 -*-
"""Tests for the JSON-LD document builders and content negotiation."""
import unittest

from odoo.addons.activitypub.models.activitypub_service import (
    AS_PUBLIC,
    build_actor_document,
    build_ordered_collection,
    build_ordered_collection_page,
    build_webfinger,
    wants_activitypub,
)

ACTOR_URL = "https://news.example.com/ap/actors/7"


class TestWebFinger(unittest.TestCase):
    def test_subject_and_self_link(self):
        doc = build_webfinger("news", "news.example.com", ACTOR_URL)
        self.assertEqual(doc["subject"], "acct:news@news.example.com")
        self_links = [l for l in doc["links"] if l["rel"] == "self"]
        self.assertEqual(len(self_links), 1)
        self.assertEqual(self_links[0]["type"], "application/activity+json")
        self.assertEqual(self_links[0]["href"], ACTOR_URL)


class TestActorDocument(unittest.TestCase):
    def _doc(self, **over):
        kw = dict(
            actor_url=ACTOR_URL, username="news", name="Example News",
            actor_type="Service", public_pem="-----BEGIN PUBLIC KEY-----\nx\n-----END PUBLIC KEY-----\n",
            inbox_url=ACTOR_URL + "/inbox", outbox_url=ACTOR_URL + "/outbox",
            followers_url=ACTOR_URL + "/followers", following_url=ACTOR_URL + "/following",
            shared_inbox_url="https://news.example.com/ap/inbox",
        )
        kw.update(over)
        return build_actor_document(**kw)

    def test_required_members(self):
        doc = self._doc()
        for key in ("@context", "id", "type", "preferredUsername", "inbox",
                    "outbox", "followers", "publicKey"):
            self.assertIn(key, doc)
        self.assertEqual(doc["id"], ACTOR_URL)
        self.assertEqual(doc["type"], "Service")
        self.assertEqual(doc["publicKey"]["id"], ACTOR_URL + "#main-key")
        self.assertEqual(doc["publicKey"]["owner"], ACTOR_URL)
        self.assertIn("BEGIN PUBLIC KEY", doc["publicKey"]["publicKeyPem"])
        self.assertEqual(doc["endpoints"]["sharedInbox"],
                         "https://news.example.com/ap/inbox")

    def test_context_has_security_vocab(self):
        doc = self._doc()
        self.assertIn("https://w3id.org/security/v1", doc["@context"])

    def test_optional_members_omitted_when_empty(self):
        doc = self._doc()
        self.assertNotIn("summary", doc)
        self.assertNotIn("icon", doc)

    def test_optional_members_present_when_given(self):
        doc = self._doc(summary_html="<p>hi</p>", icon_url="https://x/i.png")
        self.assertEqual(doc["summary"], "<p>hi</p>")
        self.assertEqual(doc["icon"], {"type": "Image", "url": "https://x/i.png"})


class TestOrderedCollections(unittest.TestCase):
    def test_collection_shape(self):
        doc = build_ordered_collection("https://x/outbox", 0, first="https://x/outbox?page=1")
        self.assertEqual(doc["type"], "OrderedCollection")
        self.assertEqual(doc["totalItems"], 0)
        self.assertEqual(doc["first"], "https://x/outbox?page=1")
        self.assertNotIn("last", doc)

    def test_page_shape(self):
        page = build_ordered_collection_page(
            "https://x/outbox?page=1", "https://x/outbox", ["a", "b"],
            next_url="https://x/outbox?page=2")
        self.assertEqual(page["type"], "OrderedCollectionPage")
        self.assertEqual(page["partOf"], "https://x/outbox")
        self.assertEqual(page["orderedItems"], ["a", "b"])
        self.assertEqual(page["next"], "https://x/outbox?page=2")


class TestContentNegotiation(unittest.TestCase):
    def test_browser_accept_is_html(self):
        self.assertFalse(wants_activitypub(
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"))

    def test_empty_accept_is_html(self):
        self.assertFalse(wants_activitypub(""))

    def test_activity_json_accept(self):
        self.assertTrue(wants_activitypub("application/activity+json"))

    def test_ld_json_accept(self):
        self.assertTrue(wants_activitypub(
            'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'))

    def test_public_uri_constant(self):
        self.assertEqual(AS_PUBLIC, "https://www.w3.org/ns/activitystreams#Public")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
