# Idiot Chat

A small Python desktop assistant. Press **Watch and Chat** to share your screen and microphone with an AI, then **Stop** to end capture. Nothing is captured before activation. It uses native Tkinter and an OpenAI-compatible vision and transcription API.

## Install and run

Use Python 3.9 or newer, preferably a current **python.org macOS installer**, which includes Tk. Apple's system Python has an old Tk and is not recommended. Homebrew Python needs its matching `python-tk` formula. Verify your chosen interpreter first:

```sh
python3 -c 'import tkinter; print(tkinter.TkVersion)'
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[voice]'
python -m idiot_chat
```

The installed `idiot-chat` command opens the same application. A logged-in graphical desktop is required. If importing Tk fails, install a Python distribution with Tk, recreate the virtual environment with that interpreter, and reinstall.

### Microphone setup

```sh
# macOS, only if PortAudio is missing:
brew install portaudio
python -m pip install -e '.[voice]'
```

Watch and Chat opens the default microphone and immediately speaks “What do you need help with?”. Answer naturally. A local volume detector identifies speech onset and approximately 700 ms of trailing silence; each completed utterance is transcribed and sent with a fresh screenshot. There are no repeated screen-only requests during silence. Input is bounded to 30 seconds per turn. Speak again to interrupt synthesis/playback and invalidate an outstanding reply, without pressing anything. Use headphones: there is no acoustic echo cancellation, so loudspeaker output can trigger barge-in. Quiet speech or noisy rooms may need input-level adjustment.

This is turn-based transcription, not true streaming audio or streaming model output. Speech onset is checked every 60 ms, independently of model workers. HTTP requests already sent cannot be recalled: they finish in background, but cancelled turns cannot publish text or start playback. Stop closes the microphone and stops future screenshots and speech. Restart does not wait for an old HTTP timeout.

### Edge TTS and voices

The `voice` extra installs `edge-tts`, `sounddevice` and NumPy. Edge TTS uses an online Microsoft service without an API key; it requires internet access and sends reply text to that service. Availability and service terms can change. macOS playback uses `/usr/bin/afplay`; Linux/Windows require `ffplay` on PATH (install FFmpeg). Synthesis and playback run off the Tk thread, and cancellation terminates their subprocesses. Temporary MP3 files are removed when the speech worker exits.

**Edge TTS voice** defaults to `en-GB-SoniaNeural`. Select a suggested UK/US voice or type another installed service voice name. To discover the full online catalogue run `python -m edge_tts --list-voices`. The preference is saved when you start, in `~/.config/idiot-chat/settings.json` (override with `IDIOT_CHAT_SETTINGS`). Only the voice is persisted, never the API key. **Speak replies** is on by default; **Mute** disables it for the current app instance. TTS errors leave visible replies intact and show a status notice. The replaceable provider interface is `Speaker.speak(text, voice, cancel_event)` plus `stop()` in `voice.py`.

## Configure

Enter the API base URL, chat/vision model and API key in the window **while stopped**, then click **Watch and Chat**. The key is masked; API settings are held in memory and never written to a configuration file. A key can be empty for a local server that does not require authentication. The base URL must include any provider prefix, such as `/v1`; do not include `/chat/completions`.

You can also set environment variables before launching:

| Variable | Default | Purpose |
| --- | --- | --- |
| `IDIOT_CHAT_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API root |
| `IDIOT_CHAT_MODEL` | `gpt-4o-mini` | Chat model; must support images when screenshots are enabled |
| `IDIOT_CHAT_API_KEY` | unset | Bearer API key; `OPENAI_API_KEY` is a fallback |
| `IDIOT_CHAT_TRANSCRIPTION_MODEL` | `whisper-1` | Optional transcription model |
| `IDIOT_CHAT_TIMEOUT` | `60` | Request timeout in seconds, 1–180 |
| `IDIOT_CHAT_MAX_TOKENS` | `1200` | Maximum reply tokens, 1–16384 |

For a local server, for example:

```sh
export IDIOT_CHAT_BASE_URL='http://127.0.0.1:1234/v1'
export IDIOT_CHAT_MODEL='your-local-vision-model'
python -m idiot_chat
```

Use the masked field for keys to avoid putting them in shell history. The app does not load `.env` files. No credentials are included in the repository. Use HTTPS for remote services: HTTP transmits the key and content without transport encryption. Redirects are refused rather than forwarding private payloads or keys to another URL.

## Use

1. Install with `python -m pip install -e '.[voice]'`, configure the API and optionally choose, review and enable a folder.
2. Press **Watch and Chat** once. Hear the welcome and answer by speaking. Screen capture happens automatically on each spoken turn, not before activation or continuously during silence.
3. Read replies in the transcript or hear them spoken. Speak over a reply to interrupt it. Typed questions and optional folder context remain available.
4. Press **Stop** or close the window to release input and cancel speech. Late replies are suppressed. Already-sent requests and an OS screenshot already in progress cannot be recalled.

Voice turns always include a desktop frame. **Include screen in typed messages** controls typed messages only. API/capture errors stop the session with guidance; missing microphone support leaves typed chat available. The default OpenAI endpoint requires a key before devices open.

### Folder context

The indexer reads a local snapshot only when you choose/re-index a folder. It does not watch for changes. It reads recognised UTF-8 text/code formats, skips hidden files/directories, symlinks, common dependency/build folders, binary-looking content, and filenames containing common secret-related terms. This is **not a secret detector**. Review the exact text before attaching; sensitive information in an ordinary text file can still be included.

Limits: 5,000 directory entries examined, 40 included files, 6,000 characters per file and 24,000 characters overall, including relative file labels and truncation markers. The UI reports exclusions and truncation. Only this bounded excerpt is sent; no whole-folder upload or absolute folder path is included. Re-indexing resets the attach tick. **Remove folder** drops the snapshot from app memory.

### macOS permissions

Permissions belong to the application that launches Python, often Terminal or iTerm, sometimes Python or an IDE.

- **Screenshots:** System Settings → Privacy & Security → **Screen & System Audio Recording**, called **Screen Recording** on older macOS versions. Enable the launching application, then quit and reopen it. The app checks/requests this when you press Watch and Chat or send a screenshot. If the first permission prompt appears, grant access, restart, and resend. Watch and Chat requires screen permission even when you use typed messages.
- **Microphone:** System Settings → Privacy & Security → **Microphone**. Allow the launching application when you press Watch and Chat, then restart it if needed. Also check your default input device. If microphone access fails, screen and typed chat remain available.
- **Folder access:** Grant access only to the selected folder. macOS may separately request Documents/Desktop access. You do not need to grant Full Disk Access.

The capture backend is Pillow's OS screenshot implementation. It captures a whole desktop image, including the assistant window and any private windows visible at capture time; there is no window picker, redaction or screenshot preview. Multi-monitor behaviour depends on the OS/backend and has not been verified. On macOS Pillow may use a temporary image file, which its normal capture path removes. This MVP does not provide secure deletion guarantees.

## Privacy and limitations

Chat, API settings, folder snapshots, resized screenshots and microphone recordings are not deliberately persisted by the app. Closing it drops its in-memory state. macOS capture may use a temporary file as described above; operating-system swap/crash files and provider retention are outside the app's control. The API receives your question, up to 20 recent complete chat pairs within a 16,000-character history budget, and the current attachments you enable. Old screenshots and folder attachments are not replayed in conversation history. A transcription request sends recorded audio to the same configured API root. Your provider may retain data or charge for requests, including requests stopped locally.

This is a first MVP, not a signed/notarised macOS `.app`. It has no accounts, keychain integration, durable history, streaming replies, tool execution or desktop control. It cannot click or type into other applications. It only sees per-turn desktop frames during an activated session, not a continuous video stream. Screenshot and folder content are labelled as untrusted reference data, but prompt-injection resistance cannot be guaranteed.

Compatibility targets the `/chat/completions` JSON schema with `max_tokens`, bearer authentication and base64 `image_url` messages; responses must contain a string at `choices[0].message.content`. APIs requiring the Responses API, `max_completion_tokens`, custom auth or other image formats need an adapter. Voice additionally needs multipart `/audio/transcriptions` returning `{"text": "..."}`. Request errors show fixed guidance without printing server response bodies or keys. Black/partial screenshots can still occur with protected windows or OS restrictions. Voice/device quality, real provider compatibility and OS permission prompts require checking on your machine. Linux/Windows are best-effort; speech playback there needs FFmpeg.

## Tests

Core tests need only Python's standard library and do not capture a real screen, open a microphone or contact a paid API:

```sh
python -m unittest discover -s tests -v
```

To also run the desktop integration tests, install the base dependencies and use a graphical session with working Tk:

```sh
IDIOT_CHAT_GUI_TESTS=1 python -m unittest discover -s tests -v
```

Desktop tests create Tk widgets, use a synthetic screenshot and a local HTTP server, and verify activation gating, repeated screen/audio wiring, permission-error handling, microphone fallback and suppression of stopped responses. They do not verify real screen capture, microphone recording, speech playback or remote provider access.
