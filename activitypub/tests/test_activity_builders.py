# -*- coding: utf-8 -*-
"""Tests for the Create / Update / Delete / Accept activity envelopes."""
import unittest

from odoo.addons.activitypub.models.activitypub_service import (
    AS_PUBLIC,
    build_accept,
    build_create,
    build_delete,
    build_reject,
    build_update,
)

ACTOR = "https://news.example.com/ap/actors/3"
FOLLOWERS = ACTOR + "/followers"
OBJ = {"id": "https://news.example.com/ap/objects/12", "type": "Article",
       "name": "Hello"}


class TestActivityBuilders(unittest.TestCase):

    def test_create_wraps_object_and_addresses_public(self):
        act = build_create(ACTOR, OBJ, activity_id=ACTOR + "/activities/1",
                           cc=[FOLLOWERS])
        self.assertEqual(act["type"], "Create")
        self.assertEqual(act["actor"], ACTOR)
        self.assertEqual(act["object"], OBJ)
        self.assertEqual(act["to"], [AS_PUBLIC])
        self.assertEqual(act["cc"], [FOLLOWERS])
        self.assertIn("published", act)
        self.assertEqual(act["@context"], "https://www.w3.org/ns/activitystreams")

    def test_update_type(self):
        act = build_update(ACTOR, OBJ, activity_id=ACTOR + "/activities/2")
        self.assertEqual(act["type"], "Update")
        self.assertIn("published", act)

    def test_delete_carries_tombstone(self):
        act = build_delete(ACTOR, OBJ["id"], activity_id=ACTOR + "/activities/3",
                           cc=[FOLLOWERS])
        self.assertEqual(act["type"], "Delete")
        self.assertEqual(act["object"], {"id": OBJ["id"], "type": "Tombstone"})
        self.assertNotIn("published", act)

    def test_accept_echoes_follow(self):
        follow = {"type": "Follow", "id": "https://remote.example/f/9",
                  "actor": "https://remote.example/users/bob", "object": ACTOR}
        act = build_accept(ACTOR, follow, activity_id=ACTOR + "/activities/4")
        self.assertEqual(act["type"], "Accept")
        self.assertEqual(act["actor"], ACTOR)
        self.assertEqual(act["object"], follow)

    def test_reject_echoes_follow(self):
        follow = {"type": "Follow", "id": "https://remote.example/f/9"}
        act = build_reject(ACTOR, follow, activity_id=ACTOR + "/activities/5")
        self.assertEqual(act["type"], "Reject")
        self.assertEqual(act["object"], follow)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
