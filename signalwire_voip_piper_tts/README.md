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
  904 speakers, selectable by name via the **Speaker** field next to
  the Voice picker - see "Picking a LibriTTS-R speaker" below.

If you want a different Piper voice, check that specific voice's own
`MODEL_CARD` (on [Hugging Face](https://huggingface.co/rhasspy/piper-voices))
for its license before using it - don't assume any Piper voice is
automatically commercial-safe.

## Setup

Piper's own HTTP server has **no authentication of its own**, so run
it on a private/internal network, never exposed to the public
internet - it only needs to be reachable from your Odoo instance.
Below runs it as its own unprivileged system user (`piper`), with its
own venv and data directory, under systemd - it never needs root,
shell login, or access to anything outside its own directory.

1. **Create a dedicated, locked-down system user** (no login shell, no
   home directory outside its own service directory):
   ```
   sudo useradd --system --no-create-home --home-dir /opt/piper \
       --shell /usr/sbin/nologin piper
   sudo mkdir -p /opt/piper
   sudo chown piper:piper /opt/piper
   ```
2. **Set up its own venv and download the two voices**, as that user:
   ```
   sudo -u piper python3 -m venv /opt/piper/venv
   sudo -u piper /opt/piper/venv/bin/pip install 'piper-tts[http]'
   sudo -u piper /opt/piper/venv/bin/python3 -m piper.download_voices \
       en_US-ljspeech-medium --data-dir /opt/piper/voices
   sudo -u piper /opt/piper/venv/bin/python3 -m piper.download_voices \
       en_US-libritts_r-medium --data-dir /opt/piper/voices
   ```
3. **Create the systemd unit**, `/etc/systemd/system/piper-tts.service`:

   ```ini
   [Unit]
   Description=Piper TTS HTTP server
   After=network.target

   [Service]
   Type=simple
   User=piper
   Group=piper
   ExecStart=/opt/piper/venv/bin/python3 -m piper.http_server \
       -m en_US-ljspeech-medium --data-dir /opt/piper/voices \
       --host 127.0.0.1 --port 5000
   Restart=on-failure
   NoNewPrivileges=true
   ProtectSystem=strict
   ProtectHome=true
   ReadWritePaths=/opt/piper/voices
   PrivateTmp=true

   [Install]
   WantedBy=multi-user.target
   ```
   `--host 127.0.0.1` keeps it off the network entirely if Odoo runs
   on the same box - drop that flag (and bind to the box's private
   interface instead) if Odoo is elsewhere on the same private
   network. `-m` only sets the *default* voice; `/synthesize` accepts
   a `voice` field per request, so one running instance serves both
   downloaded voices. `ProtectSystem=strict`/`ReadWritePaths` mean
   this service can't write anywhere on disk except its own voices
   directory, even if compromised.
4. **Enable and start it**:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now piper-tts
   sudo systemctl status piper-tts
   curl http://127.0.0.1:5000/voices
   ```

   The last command should list both installed voices.
5. In Odoo, on your `signalwire.server` record, set **Piper TTS
   Server URL** to wherever that's reachable (e.g.
   `http://localhost:5000`, or the private IP if Odoo is on a
   different box). Leave it blank to keep every IVR menu/voicemail
   greeting on the plain built-in voice - Piper is entirely optional,
   nothing breaks without it.
6. On an IVR menu, a user's own voicemail Preferences, or a call
   group's own shared voicemail settings, pick a **Voice**.

## Picking a LibriTTS-R speaker

The **Speaker** field next to the Voice picker (on an IVR menu, a
user's voicemail Preferences, or a call group's shared voicemail
settings) lists all 904 by name and gender - e.g. "Kristin LeMoine
(Female)" - not a bare number. That metadata is real: LibriTTS-R's
own `speakers.tsv` (published alongside the corpus on
[OpenSLR](https://www.openslr.org/141/)) gives the gender and the
reader's registered [LibriVox](https://librivox.org/) name for every
one of Piper's 904 speaker IDs - cross-checked directly against this
voice's own `speaker_id_map` (in its `.onnx.json` config) and
confirmed a full 904/904 match, no gaps. Leave the field blank to use
LibriTTS-R's own default speaker. Ignored for LJSpeech, which only
has one voice.

**A name is not a quality guarantee** - this is real per-speaker
identity, not a curated "best of" list. Nobody's actually listened to
all 904 to rate which sound best - that's exactly what the **Preview**
button below is for.

## Previewing a voice without placing a call

Right under the Voice/Speaker fields (IVR menu, user voicemail
Preferences, call group voicemail) is a **Preview** button with its
own small text box, pre-filled with the greeting's own current text
but freely editable - type anything you want to hear and press
Preview to synthesize and play it immediately in the browser, using
whatever Voice/Speaker is currently selected on the form (even if the
record hasn't been saved yet). Nothing is saved or cached by this -
it's a one-off sample, not a permanent greeting, and it never places a
real call or touches SignalWire at all. Requires `piper_url` to be
configured and reachable; any logged-in internal user can use it (same
access level as editing your own voicemail Preferences already has).

If you'd rather script it directly (e.g. to batch-sample a handful of
speakers) Piper's own bundled web UI
(`http://<piper-host>:5000/` in a browser) doesn't offer a speaker
picker itself, but you can still hit its `/synthesize` endpoint
directly - the speaker's number is the same one used internally, kept
in `models/libritts_r_speakers.py` if you want to look one up by name:

```bash
curl -s -X POST http://127.0.0.1:5000/synthesize \
    -H "Content-Type: application/json" \
    -d '{"text": "Hello there, this is a test.", "voice": "en_US-libritts_r-medium", "speaker_id": 42}' \
    -o /tmp/speaker_42.wav
```

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

## Verification status

**Confirmed live end to end**: a real Piper server, `piper_url` set
on `signalwire.server`, a voice picked on an IVR menu, and a real
inbound call actually playing the cached Piper audio - the
`libritts_r`/`ljspeech` voices are confirmed to sound meaningfully
more natural than the plain built-in one. Per-speaker selection
(`piper_speaker_id`) and the Preview button are both covered by the
automated suite (real backend HTTP round trips) but not yet confirmed
against a real running Piper server by an actual person clicking
Preview in a browser - both came from follow-up requests after the
base module's own live call already worked, so they're newer ground.
