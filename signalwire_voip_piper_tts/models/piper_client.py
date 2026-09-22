# -*- coding: utf-8 -*-
import logging

import requests

_logger = logging.getLogger(__name__)

TIMEOUT = 30


class PiperError(Exception):
    """Raised for any Piper TTS failure - a non-2xx response, a
    network error, or an empty/unparseable audio response. Mirrors
    signalwire_voip's own SignalWireAPIError shape (same normalized-
    message discipline) - never leaks a raw response body.
    """


class PiperClient:
    """Thin wrapper over Piper's own bundled HTTP server
    (``python3 -m piper.http_server``, confirmed via its real docs -
    a single ``POST /synthesize`` endpoint, JSON in, raw WAV bytes
    out). No authentication of its own - the server is expected to
    run on a private/internal network the way this project's other
    sibling services do (meskis-deploy-agent, standalone FastAPI
    services), not directly on the public internet.
    """

    def __init__(self, base_url):
        self.base_url = (base_url or '').rstrip('/')

    def synthesize(self, text, voice):
        """Returns raw WAV bytes for `text` spoken in `voice` (a
        Piper voice name, e.g. "en_US-ljspeech-medium"). Raises
        PiperError on any failure - callers decide whether that's
        fatal (a config-time save) or something to swallow and fall
        back from (never true for this method itself, always true for
        its callers on the live call path - see signalwire.piper.
        audio.cache.get_cached, which never calls this at all).
        """
        if not self.base_url:
            raise PiperError("No Piper server URL configured.")
        try:
            response = requests.post(
                f'{self.base_url}/synthesize',
                json={'text': text, 'voice': voice},
                timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise PiperError(f'Could not reach Piper: {exc}') from exc

        if response.status_code >= 400:
            raise PiperError(
                f'Piper returned {response.status_code}: '
                f'{response.text[:200] or "(no body)"}')
        if not response.content:
            raise PiperError("Piper returned an empty response.")
        return response.content
