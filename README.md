# Idiot Chat

A small Python desktop assistant with explicit Start/Stop sessions, typed chat and on-demand screenshots. It uses native Tkinter widgets and an OpenAI-compatible API. There is no background screen polling, wake word or always-on microphone.

## Install and run

Use Python 3.9 or newer, preferably a current **python.org macOS installer**, which includes Tk. Apple's system Python has an old Tk and is not recommended. Homebrew Python needs its matching `python-tk` formula. Verify your chosen interpreter first:

```sh
python3 -c 'import tkinter; print(tkinter.TkVersion)'
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m idiot_chat
```

The installed `idiot-chat` command opens the same application. A logged-in graphical desktop is required. If importing Tk fails, install a Python distribution with Tk, recreate the virtual environment with that interpreter, and reinstall.

### Optional voice input

```sh
# macOS, only if PortAudio is missing:
brew install portaudio
python -m pip install -e '.[voice]'
```

Voice input uses the default microphone through `sounddevice`, records at most 30 seconds, and uploads a WAV to your configured API's `/audio/transcriptions` endpoint only after **Finish & transcribe**. It places the transcription into the question box; it does not send a chat message automatically. **Discard recording**, **Stop session** and closing the app discard recorded audio. Reaching 30 seconds also discards the recording without uploading it. Missing dependencies, unsupported transcription or microphone permissions leave typed chat available.

Optional speech output uses macOS's local `/usr/bin/say` with installed system voices. Tick **Speak replies** to enable it. **Mute**, Stop and closing the window stop playback. It is disabled on other operating systems. No separate TTS API or key is needed.

## Configure

Enter the API base URL, chat/vision model and API key in the window **while stopped**, then click **Start session**. The key is masked; settings are held in memory and never written to a configuration file. A key can be empty for a local server that does not require authentication. The base URL must include any provider prefix, such as `/v1`; do not include `/chat/completions`.

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

1. Configure the API, read the privacy note and click **Start session**. Starting alone does not capture the screen, open the microphone or contact the API.
2. Type a question. **Attach screenshot on Send** is enabled by default and visibly labelled. Untick it for text-only chat or a model without vision support.
3. Optionally choose a folder, open **Review text to attach**, then tick **Attach selected folder text**. Selecting a folder alone sends nothing and does not enable attachment.
4. Press **Send**, Command+Return or Control+Return. One screenshot is captured at this point if enabled, resized to fit within 1600 × 1600 pixels, and sent with the question, recent conversation and any enabled folder text. Capture status is visible. There are no automatic retries.
5. Click **Stop session** to disable sends, invalidate pending results, stop speech and discard microphone audio. Stop cannot recall data already captured or sent, or cancel a request the provider is processing. Start stays disabled until an in-flight worker returns or times out. **Clear chat** removes conversation history from the app's memory.

A screenshot failure does **not** silently fall back to a text-only request: nothing is sent. The question stays in the draft so you can change permissions or untick screenshots and retry. Edits typed while waiting for a reply are preserved.

### Folder context

The indexer reads a local snapshot only when you choose/re-index a folder. It does not watch for changes. It reads recognised UTF-8 text/code formats, skips hidden files/directories, symlinks, common dependency/build folders, binary-looking content, and filenames containing common secret-related terms. This is **not a secret detector**. Review the exact text before attaching; sensitive information in an ordinary text file can still be included.

Limits: 5,000 directory entries examined, 40 included files, 6,000 characters per file and 24,000 characters overall, including relative file labels and truncation markers. The UI reports exclusions and truncation. Only this bounded excerpt is sent; no whole-folder upload or absolute folder path is included. Re-indexing resets the attach tick. **Remove folder** drops the snapshot from app memory.

### macOS permissions

Permissions belong to the application that launches Python, often Terminal or iTerm, sometimes Python or an IDE.

- **Screenshots:** System Settings → Privacy & Security → **Screen & System Audio Recording**, called **Screen Recording** on older macOS versions. Enable the launching application, then quit and reopen it. The app checks/requests this only on an explicit screenshot Send. If the first permission prompt appears, grant access, restart, and resend. No screen permission is needed for text-only chat.
- **Microphone:** System Settings → Privacy & Security → **Microphone**. Allow the launching application when you first choose Record, then restart it if needed. Also check your default input device. No microphone permission is needed for typed chat or local speech output.
- **Folder access:** Grant access only to the selected folder. macOS may separately request Documents/Desktop access. You do not need to grant Full Disk Access.

The capture backend is Pillow's OS screenshot implementation. It captures a whole desktop image, including the assistant window and any private windows visible at capture time; there is no window picker, redaction or screenshot preview. Multi-monitor behaviour depends on the OS/backend and has not been verified. On macOS Pillow may use a temporary image file, which its normal capture path removes. This MVP does not provide secure deletion guarantees.

## Privacy and limitations

Chat, settings, folder snapshots, resized screenshots and microphone recordings are not deliberately persisted by the app. Closing it drops its in-memory state. macOS capture may use a temporary file as described above; operating-system swap/crash files and provider retention are outside the app's control. The API receives your question, up to 20 recent complete chat pairs within a 16,000-character history budget, and the current attachments you enable. Old screenshots and folder attachments are not replayed in conversation history. A transcription request sends recorded audio to the same configured API root. Your provider may retain data or charge for requests, including requests stopped locally.

This is a first MVP, not a signed/notarised macOS `.app`. It has no accounts, keychain integration, durable history, streaming replies, tool execution or desktop control. It cannot click, type into other applications, monitor changes or see anything beyond an explicitly sent screenshot. Screenshot and folder content are labelled as untrusted reference data, but prompt-injection resistance cannot be guaranteed.

Compatibility targets the `/chat/completions` JSON schema with `max_tokens`, bearer authentication and base64 `image_url` messages; responses must contain a string at `choices[0].message.content`. APIs requiring the Responses API, `max_completion_tokens`, custom auth or other image formats need an adapter. Voice additionally needs multipart `/audio/transcriptions` returning `{"text": "..."}`. Request errors show fixed guidance without printing server response bodies or keys. Black/partial screenshots can still occur with protected windows or OS restrictions. Voice/device quality, real provider compatibility and OS permission prompts require checking on your machine. Linux/Windows are best-effort; local speech output is macOS-only.

## Tests

Core tests need only Python's standard library and do not capture a real screen, open a microphone or contact a paid API:

```sh
python -m unittest discover -s tests -v
```

To also run the desktop integration tests, install the base dependencies and use a graphical session with working Tk:

```sh
IDIOT_CHAT_GUI_TESTS=1 python -m unittest discover -s tests -v
```

Desktop tests create Tk widgets, use a synthetic screenshot and a local HTTP server, and verify explicit session gating, screenshot/text-only request construction, history, permission-error handling, voice fallback and suppression of stopped responses. They do not verify real screen capture, microphone recording, speech playback or remote provider access.
