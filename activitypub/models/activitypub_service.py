# -*- coding: utf-8 -*-
"""ActivityPub / Fediverse protocol helpers, deliberately free of any Odoo
import so they can be unit tested in isolation and reused from a cron worker
or a plain script.

This module covers the parts of ActivityPub that are pure data and crypto:

* RSA key generation, and the HTTP Signatures (draft-cavage-http-signatures-12)
  signing / verification that Mastodon, Pleroma, Misskey et al. require on
  every server-to-server request;
* building the JSON-LD documents Odoo serves - the WebFinger JRD, the Actor
  object, and the (still empty) paged ``OrderedCollection`` used by outboxes
  and follower lists;
* content negotiation - deciding whether a caller wants the ActivityPub JSON
  representation of a URL or the human web page at the same address.

Only depends on ``cryptography`` (bundled with Odoo). ``requests`` is used by
the ORM layer for delivery, not here.
"""
import base64
import hashlib
import re
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# The two JSON-LD vocabularies every mainstream Fediverse server agrees on:
# ActivityStreams 2.0 for the social vocabulary, and the security vocab for
# the ``publicKey`` / ``publicKeyPem`` terms HTTP Signatures are described in.
AS_CONTEXT = [
    "https://www.w3.org/ns/activitystreams",
    "https://w3id.org/security/v1",
]

# The magic "everyone" collection: the presence of this URI in ``to`` / ``cc``
# is what makes a post public and boostable.
AS_PUBLIC = "https://www.w3.org/ns/activitystreams#Public"

# ``activity+json`` is what Mastodon actually sends and expects; ``ld+json``
# with the AS profile is the spec's SHOULD. We emit the former and accept
# either.
AP_CONTENT_TYPE = "application/activity+json"

# Local part of a handle: kept deliberately strict so it round-trips through
# WebFinger, URLs and other servers' own validation without surprises.
USERNAME_RE = re.compile(r"^[a-z0-9_-]{1,64}$")

# Inbound requests whose (signed) Date header is further than this from our
# clock are rejected, so a captured request cannot be replayed indefinitely.
MAX_CLOCK_SKEW_SECONDS = 3600


class ActivityPubError(Exception):
    """Base class for anything these helpers reject."""


class SignatureError(ActivityPubError):
    """An HTTP Signature is missing, malformed, stale, or does not verify."""


# --------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------
def generate_rsa_keypair(key_size=2048):
    """Return a fresh ``(private_pem, public_pem)`` pair as ``str``.

    2048-bit RSA is the Fediverse de-facto floor: some servers reject smaller
    keys, and larger ones only cost more per request for no interop gain. The
    private key is PKCS#8, the public key SubjectPublicKeyInfo - the encodings
    every other implementation expects to parse out of ``publicKeyPem``.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem


# --------------------------------------------------------------------------
# HTTP Signatures (draft-cavage-http-signatures-12)
# --------------------------------------------------------------------------
def digest_header(body):
    """``SHA-256=<base64(sha256(body))>`` - binds a signature to the exact
    request body so it cannot be swapped after signing."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    return "SHA-256=" + base64.b64encode(hashlib.sha256(body or b"").digest()).decode("ascii")


def _signing_string(method, path, headers, signed_names):
    lines = []
    for name in signed_names:
        if name == "(request-target)":
            lines.append(f"(request-target): {method.lower()} {path}")
        else:
            lines.append(f"{name}: {headers[name]}")
    return "\n".join(lines)


def _titlecase_header(name):
    return "-".join(part.capitalize() for part in name.split("-"))


def build_signature_headers(method, url, key_id, private_pem, body=b"",
                            extra_headers=None, now=None):
    """Return the full header set for an outbound server-to-server request,
    ``Signature`` included.

    For a POST (delivering an activity) the signed set is
    ``(request-target) host date digest``; for a signed GET (dereferencing a
    remote actor in "secure mode") it is ``(request-target) host date``.
    ``now`` is injectable for tests.
    """
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    when = now or datetime.now(timezone.utc)
    headers = {
        "host": parsed.netloc,
        "date": format_datetime(when, usegmt=True),
    }
    if method.upper() == "POST":
        headers["digest"] = digest_header(body)
        headers["content-type"] = AP_CONTENT_TYPE
    if extra_headers:
        headers.update({k.lower(): v for k, v in extra_headers.items()})

    signed_names = ["(request-target)", "host", "date"]
    if "digest" in headers:
        signed_names.append("digest")

    signing_string = _signing_string(method, path, headers, signed_names)
    key = serialization.load_pem_private_key(private_pem.encode("ascii"), password=None)
    signature = key.sign(signing_string.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    headers["signature"] = (
        f'keyId="{key_id}",algorithm="rsa-sha256",'
        f'headers="{" ".join(signed_names)}",'
        f'signature="{base64.b64encode(signature).decode("ascii")}"'
    )
    return {_titlecase_header(k): v for k, v in headers.items()}


def parse_signature_header(value):
    """Parse ``keyId="..",algorithm="..",headers="..",signature=".."`` into a
    dict, filling in the documented defaults. Raises :class:`SignatureError`
    when the required members are absent."""
    if not value:
        raise SignatureError("missing Signature header")
    parts = {m.group(1): m.group(2)
             for m in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', value)}
    if "keyId" not in parts or "signature" not in parts:
        raise SignatureError("Signature header missing keyId or signature")
    parts.setdefault("headers", "date")
    parts.setdefault("algorithm", "rsa-sha256")
    return parts


def _digest_matches(received, computed):
    def members(v):
        out = {}
        for chunk in (v or "").split(","):
            algo, _sep, digest = chunk.strip().partition("=")
            if algo:
                out[algo.lower()] = digest
        return out
    r, c = members(received), members(computed)
    return "sha-256" in r and r["sha-256"] == c.get("sha-256")


def verify_signature(method, path, headers, body, public_pem, now=None):
    """Verify an inbound request's HTTP Signature against ``public_pem``.

    ``headers`` is any mapping of the request headers as received (matched
    case-insensitively). ``path`` must be the exact request target including
    query string. Raises :class:`SignatureError` on any failure; returns the
    parsed signature dict (with ``keyId`` etc.) on success.
    """
    lower = {k.lower(): v for k, v in headers.items()}
    sig = parse_signature_header(lower.get("signature"))
    # ``hs2019`` is the draft-12 rename; in practice everyone still sends
    # rsa-sha256 and nothing but RSA keys, so that is all we accept.
    if sig["algorithm"] not in ("rsa-sha256", "hs2019"):
        raise SignatureError(f"unsupported signature algorithm {sig['algorithm']!r}")

    signed_names = sig["headers"].split()
    if "(request-target)" not in signed_names or "date" not in signed_names:
        raise SignatureError("signature must cover at least (request-target) and date")

    # Freshness. The Date header is part of the signed set, so checking it
    # here is what actually stops a replay of a captured request.
    try:
        sent = parsedate_to_datetime(lower["date"])
    except (KeyError, TypeError, ValueError):
        raise SignatureError("missing or unparseable Date header")
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    if abs((ref - sent).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
        raise SignatureError("Date header outside acceptable clock skew")

    # If the body digest is covered, it must match the body we actually got.
    if "digest" in signed_names:
        if not _digest_matches(lower.get("digest", ""), digest_header(body)):
            raise SignatureError("Digest header does not match the request body")

    build = {}
    for name in signed_names:
        if name == "(request-target)":
            continue
        if name not in lower:
            raise SignatureError(f"signed header {name!r} is not present on the request")
        build[name] = lower[name]
    signing_string = _signing_string(method, path, build, signed_names)

    try:
        key = serialization.load_pem_public_key(public_pem.encode("ascii"))
        key.verify(
            base64.b64decode(sig["signature"]),
            signing_string.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SignatureError(f"signature verification failed: {exc}")
    return sig


# --------------------------------------------------------------------------
# JSON-LD document builders
# --------------------------------------------------------------------------
def _as_utc_iso(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def build_webfinger(username, host, actor_url):
    """The JRD served at ``/.well-known/webfinger?resource=acct:user@host``.

    The ``self`` link with type ``application/activity+json`` is the one every
    client follows to discover the actor.
    """
    return {
        "subject": f"acct:{username}@{host}",
        "aliases": [actor_url],
        "links": [
            {"rel": "self", "type": AP_CONTENT_TYPE, "href": actor_url},
            {"rel": "http://webfinger.net/rel/profile-page",
             "type": "text/html", "href": actor_url},
        ],
    }


def build_actor_document(*, actor_url, username, name, actor_type, public_pem,
                         inbox_url, outbox_url, followers_url, following_url,
                         shared_inbox_url, summary_html=None, icon_url=None,
                         published=None, manually_approves_followers=False):
    """An ActivityStreams Actor object. ``publicKey.publicKeyPem`` is what
    remote servers fetch to verify this actor's HTTP Signatures."""
    doc = {
        "@context": AS_CONTEXT,
        "id": actor_url,
        "type": actor_type,
        "preferredUsername": username,
        "name": name,
        "url": actor_url,
        "inbox": inbox_url,
        "outbox": outbox_url,
        "followers": followers_url,
        "following": following_url,
        "manuallyApprovesFollowers": bool(manually_approves_followers),
        "discoverable": True,
        "endpoints": {"sharedInbox": shared_inbox_url},
        "publicKey": {
            "id": f"{actor_url}#main-key",
            "owner": actor_url,
            "publicKeyPem": public_pem,
        },
    }
    if summary_html:
        doc["summary"] = summary_html
    if icon_url:
        doc["icon"] = {"type": "Image", "url": icon_url}
    if published:
        doc["published"] = _as_utc_iso(published)
    return doc


def build_ordered_collection(collection_id, total_items, *, first=None, last=None):
    doc = {
        "@context": AS_CONTEXT[0],
        "id": collection_id,
        "type": "OrderedCollection",
        "totalItems": int(total_items),
    }
    if first:
        doc["first"] = first
    if last:
        doc["last"] = last
    return doc


def build_ordered_collection_page(page_id, part_of, ordered_items,
                                  *, next_url=None, prev_url=None):
    doc = {
        "@context": AS_CONTEXT[0],
        "id": page_id,
        "type": "OrderedCollectionPage",
        "partOf": part_of,
        "orderedItems": list(ordered_items),
    }
    if next_url:
        doc["next"] = next_url
    if prev_url:
        doc["prev"] = prev_url
    return doc


def wants_activitypub(accept_header):
    """True when an ``Accept`` header asks for ActivityPub JSON rather than
    HTML. Actor and object URLs have both a machine and a human representation
    at the same address, and this is how we tell them apart."""
    if not accept_header:
        return False
    accept = accept_header.lower()
    if "activity+json" in accept or "ld+json" in accept:
        return True
    return False
