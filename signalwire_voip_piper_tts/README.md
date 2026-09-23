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
all 904 to rate which sound best, and Piper's own bundled web UI
(`http://<piper-host>:5000/` in a browser) has no speaker picker
either - it only displays the total count. If you want to actually
hear a specific speaker before committing to it, synthesize it
directly and listen (the speaker's number is the same one used
internally - open the module's `models/libritts_r_speakers.py` to
look up a name's own numeric id, or just try a name in the field and
listen to the result on a real call):

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
(`piper_speaker_id`) is covered by the automated suite but not yet
confirmed on a real call - the speaker-selection UI came from a
follow-up request after the base module's own live call already
worked, so it's newer ground.
