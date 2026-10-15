# Idiot Chat

A small Python desktop assistant. Press **Watch and Chat** to share your screen and microphone with an AI, then **Stop** to end capture. Nothing is captured before activation. It uses native Tkinter and an OpenAI-compatible vision and transcription API.

## Before you start

You need a logged-in desktop, a microphone, headphones (recommended to prevent the app hearing itself), an internet connection, Git and Python with Tk. macOS is the primary target; Linux and Windows are best-effort. Python 3.9 is the declared minimum; use a current supported Python for a new installation. This is a Terminal-launched app, not a downloadable `.app`.

For the default OpenAI setup, create an API key at <https://platform.openai.com/api-keys> and enable API billing/credit on that account. A ChatGPT subscription does not include API usage. The default models are `gpt-4o-mini` for images/chat and `whisper-1` for transcription; your account must have access to both. Other providers must support both API routes described under [Compatibility](#compatibility). A chat-only local server will not provide voice input.

## Install and run

Use Python 3.9 or newer, preferably a current **python.org macOS installer**, which includes Tk. Apple's system Python has an old Tk and is not recommended. Homebrew Python needs its matching `python-tk` formula. Verify your chosen interpreter first:

Install Git if needed (`git --version` checks it; on macOS, `xcode-select --install` installs Apple's command-line tools). Then open Terminal and run these commands one line at a time. If you already cloned the repo, `cd` into that folder and skip the first two lines.

```sh
git clone https://github.com/mia-oc/idiot-chat.git
cd idiot-chat
python3 -c 'import tkinter; print(tkinter.TkVersion)'
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[voice]'
python -m idiot_chat
```

If `python3` points to a different installation, substitute the full path to your chosen Tk-capable Python in the check and `venv` commands above. Leave the later `python` commands unchanged: they use the activated environment.

The installed `idiot-chat` command opens the same application. A logged-in graphical desktop is required. If importing Tk fails, install a Python distribution with Tk, recreate the virtual environment with that interpreter, and reinstall.

### Open it again later

In a new Terminal window, enter the folder where you cloned the repo (for example `cd ~/Projects/idiot-chat` if that is where you put it), then:

```sh
source .venv/bin/activate
python -m idiot_chat
```

Leave Terminal open while the app is running. **Stop** ends the active session but keeps the window open; closing the window exits. API settings must be entered again after relaunch unless supplied through environment variables.

### First conversation

1. In **API settings**, keep `https://api.openai.com/v1`, `gpt-4o-mini` and `whisper-1` for OpenAI. Paste your key into **API key**. For another provider, replace the URL and both model names before starting.
2. Choose an **Edge TTS voice** in the same settings panel. Leave **Speak replies (Edge TTS)** ticked. Put on headphones and close any private windows you do not want included in screenshots.
3. Click **Watch and Chat**. It should say “What do you need help with?”. Speak your question, then pause. On the first spoken question, allow screen-recording access if macOS requests it; follow the restart instructions below. Allow microphone access when requested.
4. Wait for the visible reply and speech. Ask another question or start speaking over a reply to interrupt it. Click **Stop** when finished.

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

**Edge TTS voice** defaults to `en-GB-SoniaNeural`. Select a suggested UK/US voice or type another voice name from the online catalogue. To discover the full online catalogue run `python -m edge_tts --list-voices`. The preference is saved when you start, in `~/.config/idiot-chat/settings.json` (override with `IDIOT_CHAT_SETTINGS`). Only the voice is persisted, never the API key. **Speak replies** is on by default; **Mute** stops current speech and unticks it for the current app instance. Tick **Speak replies (Edge TTS)** again to unmute. Mute does not stop the microphone, screenshots or API requests; use **Stop** for that. TTS errors leave visible replies intact and show a status notice. Only the first 12,000 characters of a reply are spoken; the visible reply is not shortened. If speech fails, the welcome or answer remains visible, so you can still speak or type.

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

**Typed chat:** Start a session first, enter a question at the bottom, then click **Send** (or Command+Return / Control+Return). Untick **Include screen in typed messages** for text-only questions. The microphone remains live if it opened successfully, even while typing or muted; speaking may interrupt a typed request. There is no separate microphone-off control. **Clear chat** clears the visible transcript and model conversation history, not the selected folder or API settings. **Stop** keeps chat history for the next session; close the window to discard it all.

### Folder context

While stopped, click **Choose / re-index folder…**, choose a folder, click **Review text to attach**, then tick **Attach selected folder text** only if the preview is safe to send. Folder selection/removal is disabled while the microphone is active. Stop first to change it.

The indexer reads a local snapshot only when you choose/re-index a folder. It does not watch for changes. It reads recognised UTF-8 text/code formats, skips hidden files/directories, symlinks, common dependency/build folders, binary-looking content, and filenames containing common secret-related terms. This is **not a secret detector**. Review the exact text before attaching; sensitive information in an ordinary text file can still be included.

Limits: 5,000 directory entries examined, 40 included files, 6,000 characters per file and 24,000 characters overall, including relative file labels and truncation markers. The UI reports exclusions and truncation. Only this bounded excerpt is sent; no whole-folder upload or absolute folder path is included. Re-indexing resets the attach tick. **Remove folder** drops the snapshot from app memory.

### macOS permissions

Permissions belong to the application that launches Python, often Terminal or iTerm, sometimes Python or an IDE.

- **Screenshots:** System Settings → Privacy & Security → **Screen & System Audio Recording**, called **Screen Recording** on older macOS versions. Enable the launching application, then quit and reopen it. The app checks/requests this on the first spoken turn or screenshot-enabled typed message. If the first permission prompt appears, grant access, restart, and resend. Starting alone does not take a screenshot or request screen permission. Voice turns always need screen permission; typed turns need it only when **Include screen in typed messages** is ticked.
- **Microphone:** System Settings → Privacy & Security → **Microphone**. Allow the launching application when you press Watch and Chat, then restart it if needed. Also check your default input device. If microphone access fails, screen and typed chat remain available.
- **Folder access:** Grant access only to the selected folder. macOS may separately request Documents/Desktop access. You do not need to grant Full Disk Access.

The capture backend is Pillow's OS screenshot implementation. It captures a whole desktop image, including the assistant window and any private windows visible at capture time; there is no window picker, redaction or screenshot preview. Multi-monitor behaviour depends on the OS/backend and has not been verified. On macOS Pillow may use a temporary image file, which its normal capture path removes. This MVP does not provide secure deletion guarantees.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| `git` missing | On macOS run `xcode-select --install`, complete the installer, then reopen Terminal. |
| `No module named tkinter` or `_tkinter` | Install current Python from python.org, or the matching Homebrew `python-tk` formula. Recreate `.venv` with that interpreter and reinstall. Verify Tk with the check above first. |
| `No module named idiot_chat` | Enter the cloned `idiot-chat` folder, activate `.venv`, and rerun `python -m pip install -e '.[voice]'`. |
| No desktop window / display error | Run in a logged-in graphical desktop, not a headless SSH session. |
| Cannot open microphone / PortAudio missing | Follow the Microphone permission instructions; select the correct input in macOS Sound settings. If needed, run `brew install portaudio` and reinstall the voice extra. Stop and restart the session. |
| Never sends speech, cuts words, or interrupts itself | Check input volume and background noise. Use headphones. Detection uses a fixed volume threshold, not an adjustable in-app setting; it ends a turn after about 700 ms of silence or 30 seconds. |
| Screen capture fails or looks black | Grant screen permission to the launching app, quit/reopen it and restart Idiot Chat. Protected windows may remain black. The spoken turn is not sent if screenshot capture fails. |
| No welcome / no spoken answer | Check **Speak replies (Edge TTS)**, output volume, internet access and the status notice. Choose a valid catalogue voice while stopped. Reinstall the voice extra if necessary. Text replies remain available. |
| HTTP 401 / 403 | Check the API key, billing and access to both configured models. Stop before editing settings. |
| HTTP 404 / 400 | Check the provider's base URL (including `/v1` where required), vision model and transcription route. A chat model alone is not enough for voice. |
| HTTP 429 / timeout | Check API quota, network and provider status. There are no automatic retries. Fix the problem, then restart the session. |
| A reply seems slow | Each turn waits for silence, a screenshot, transcription, a complete model reply, then Edge synthesis before playback. This is not a realtime audio connection. |

For a speech-only connectivity check (no microphone or screen capture), run `python -m edge_tts --list-voices`. This contacts Microsoft; failure points to voice-service/network/dependency trouble, not your OpenAI key.

## Privacy, cost and limitations

Every spoken turn can incur transcription plus image/chat API charges. Typed turns incur chat and any enabled image charges. Check your provider's current prices and spending controls; the app has no cost estimate, budget cap or usage dashboard. Edge TTS needs no key, but still uses an external online service. A local chat/transcription server does not make the whole app offline while spoken replies are enabled.

The microphone listens throughout an active session. Audio below the detector threshold is ignored; detected utterances are buffered locally, then uploaded for transcription. It does not use a wake word. Screenshots happen per submitted spoken turn, not as continuous video. Stop before a private conversation or switching to sensitive windows.

Chat, API settings, folder snapshots, resized screenshots and microphone recordings are not deliberately persisted by the app. Closing it drops its in-memory state. macOS capture may use a temporary file as described above; operating-system swap/crash files and provider retention are outside the app's control. The API receives your question, up to 20 recent complete chat pairs within a 16,000-character history budget, and the current attachments you enable. Old screenshots and folder attachments are not replayed in conversation history. A transcription request sends recorded audio to the same configured API root. Your provider may retain data or charge for requests, including requests stopped locally.

This is a first MVP, not a signed/notarised macOS `.app`. It has no accounts, keychain integration, durable history, streaming replies, tool execution or desktop control. It cannot click or type into other applications. It only sees per-turn desktop frames during an activated session, not a continuous video stream. Screenshot and folder content are labelled as untrusted reference data, but prompt-injection resistance cannot be guaranteed.

### Compatibility

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

Desktop tests create Tk widgets, use synthetic screenshots, mock microphone/speech providers and a local HTTP server, and verify activation gating, screen/audio wiring, permission-error handling, microphone fallback, minimum-window layout and suppression of stopped responses. Core tests also check barge-in, stale-response suppression, voice preference persistence and cancellation of mocked speech subprocesses. They do not verify real screen capture, microphone recording, speech playback or remote provider access.
