# -*- coding: utf-8 -*-
import hashlib
import logging

from odoo import api, fields, models

from .piper_client import PiperError

_logger = logging.getLogger(__name__)


class SignalWirePiperAudioCache(models.Model):
    """One synthesized WAV per (voice, text) pair, shared across every
    IVR menu/voicemail box using Piper - if two different IVR menus
    both pick the same voice, their identical fixed "no selection"/
    "invalid option" messages are synthesized once and reused, not
    duplicated per menu.

    Deliberately split into two very different-shaped methods:
    `get_cached` is a pure, fast, read-only lookup safe to call from
    the live inbound-call path (never makes an HTTP call, never
    blocks a real phone call on Piper being up); `get_or_synthesize`
    is the config-time (menu/voicemail save) method that actually
    calls Piper when nothing's cached yet, and is never called from
    the call-handling controller at all.
    """
    _name = 'signalwire.piper.audio.cache'
    _description = 'SignalWire Piper TTS Audio Cache'

    voice = fields.Char(required=True)
    text = fields.Text(required=True)
    cache_key = fields.Char(required=True, index=True)
    audio_attachment_id = fields.Many2one(
        'ir.attachment', required=True, ondelete='cascade')

    _cache_key_unique = models.Constraint(
        'unique(cache_key)',
        "This voice/text combination is already cached.",
    )

    @api.model
    def _make_cache_key(self, voice, text):
        # A hash-backed key, not a unique constraint directly on the
        # (voice, text) columns themselves - text is unbounded, and a
        # btree index has a real per-value size limit; hashing sidesteps
        # that entirely regardless of how long a greeting ever gets.
        digest = hashlib.sha1(f'{voice}\n{text}'.encode()).hexdigest()
        return digest

    def get_cached(self, voice, text):
        """Read-only - never synthesizes, never calls Piper. Returns
        the cached ir.attachment, or an empty recordset if nothing's
        cached (Piper never configured, or the one synthesis attempt
        for this text failed) - the caller (the live call controller)
        always falls back to the plain built-in voice in that case.
        """
        if not voice:
            return self.env['ir.attachment']
        key = self._make_cache_key(voice, text or '')
        row = self.sudo().search([('cache_key', '=', key)], limit=1)
        if row and row.audio_attachment_id.exists():
            return row.audio_attachment_id
        return self.env['ir.attachment']

    def get_or_synthesize(self, voice, text):
        """Eager, config-time lookup-or-create - called when a
        greeting's own text/voice is saved, never from a live call.
        Returns the attachment, or an empty recordset if Piper isn't
        configured or synthesis failed - logged, never raised, so
        saving an IVR menu/voicemail preference is never blocked on
        Piper being reachable.
        """
        if not voice:
            return self.env['ir.attachment']
        text = text or ''
        cached = self.get_cached(voice, text)
        if cached:
            return cached
        server = self.env['signalwire.server'].sudo().search([], limit=1)
        if not server or not server.piper_url:
            return self.env['ir.attachment']
        try:
            wav_bytes = server._get_piper_client().synthesize(text, voice)
        except PiperError:
            _logger.exception("Piper: failed to synthesize audio for voice %s", voice)
            return self.env['ir.attachment']
        key = self._make_cache_key(voice, text)
        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'piper-{voice}-{key[:12]}.wav',
            'type': 'binary', 'raw': wav_bytes, 'mimetype': 'audio/wav',
        })
        self.sudo().create({
            'voice': voice, 'text': text, 'cache_key': key,
            'audio_attachment_id': attachment.id,
        })
        return attachment
