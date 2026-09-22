# SignalWire Piper TTS

Replaces the robotic default voice on IVR menu greetings and
voicemail greetings with a genuinely open-source, self-hosted TTS
engine - [Piper](https://github.com/OHF-Voice/piper1-gpl) - instead
of SignalWire's own paid Amazon Polly/Google Cloud/Azure/etc. voices.

## Why Piper, and which fork

The original `rhasspy/piper` repo is archived (read-only, no longer
maintained). Active development moved to
[`OHF-Voice/piper1-gpl`](https://github.com/OHF-Voice/piper1-gpl) -
maintained by the Open Home Foundation (the org behind Home
Assistant's own voice stack), genuinely active (checked directly via
the GitHub API before building this: commits within the last two
weeks, regular releases). License is GPL-3.0-or-later. This module
never imports or links Piper's own code - it calls a genuinely
separate network service over plain HTTP, the same arm's-length shape
already used elsewhere in this project for other sibling services.

## A real licensing catch - read this before picking a voice

Piper's catalog spans many languages and many individually-licensed
voice models - licensing is **per-voice**, not blanket. Piper's own
documentation example voice, `lessac`, turns out to **explicitly
prohibit commercial use** - its source corpus license states
commercial use is "strictly prohibited," specifically naming "the
development, marketing, commercialisation, sale or licencing of voice
synthesis... products." That is exactly what a business IVR is. This
was checked directly against the real license page before this module
was built, not assumed from Piper's own docs.

This module is scoped to two voices, individually checked and
confirmed clean for commercial use:

- **`ljspeech`** - public domain (the classic LJSpeech dataset), one
  voice.
- **`libritts_r`** - CC BY 4.0 (commercial use explicitly permitted,
  attribution required - see the [LibriTTS-R project](https://google.github.io/df-conformer/librittsr/)),
  904 speakers (this module uses the default speaker only - picking
  specific good speaker IDs needs someone to actually listen to
  samples, a natural follow-up, not built here).

If you want a different Piper voice, check that specific voice's own
`MODEL_CARD` (on [Hugging Face](https://huggingface.co/rhasspy/piper-voices))
for its license before using it - don't assume any Piper voice is
automatically commercial-safe.

## Setup

1. On a server reachable from your Odoo instance (can be the same
   box, or a separate one - Piper's own HTTP server has **no
   authentication of its own**, so keep it on a private/internal
   network, never exposed to the public internet):
   ```
   pip install piper-tts[http]
   python3 -m piper.download_voices en_US-ljspeech-medium
   python3 -m piper.download_voices en_US-libritts_r-medium
   python3 -m piper.http_server -m en_US-ljspeech-medium --data-dir .
   ```
   Run this as a real, persistent service (a systemd unit, same as
   any other long-running service in this project) - `--data-dir`
   just needs to contain both downloaded voices; `-m` only sets the
   *default* voice, `/synthesize` accepts a `voice` field per request
   for either one.
2. In Odoo, on your `signalwire.server` record, set **Piper TTS
   Server URL** to wherever that's reachable (e.g.
   `http://localhost:5000`). Leave it blank to keep every IVR menu/
   voicemail greeting on the plain built-in voice - Piper is entirely
   optional, nothing breaks without it.
3. On an IVR menu, a user's own voicemail Preferences, or a call
   group's own shared voicemail settings, pick a **Voice**.

## How it works

Synthesis happens **eagerly**, when a greeting's text or voice choice
is saved - never during a live call. Saving computes and caches the
actual audio (shared across every menu/mailbox using the same voice
and text - two IVR menus with the same voice never synthesize their
identical "no selection"/"invalid option" messages twice). A real
inbound call only ever checks whether audio is already cached for the
current text and voice; if Piper was never configured, or a
synthesis attempt failed, or the text changed since the last
successful sync, it falls back to the plain built-in voice instead -
**a phone call is never blocked waiting on Piper**.

## Not yet live-verified

Automated tests confirm the plumbing end to end against a mocked
Piper server - they can't confirm what a real synthesized greeting
actually sounds like. That needs a real Piper server actually running
and one real call placed against a Piper-enabled IVR menu or
voicemail box.
