"""Native Tk desktop UI. All widget access stays on the main thread."""
import queue
import threading
from dataclasses import replace

from .api import APIError, Client, build_messages
from .capture import CaptureError, capture_screen
from .config import Config, load_voice, save_voice
from .context import index_folder
from .session import Session
from .voice import Recorder, Speaker, VoiceError, VOICES


class App:
    def __init__(self, root, config=None):
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText
        self.tk, self.ttk = tk, ttk
        self.root = root
        self.root.title('Idiot Chat')
        self.root.geometry('1000x900')
        self.root.minsize(760, 700)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.config = config or Config()
        self.session = Session()
        self.recorder, self.speaker = Recorder(), Speaker()
        self.events = queue.Queue()
        self.busy = False
        self.indexing = False
        self.closed = False
        self.history = []
        self.watch_after = None
        self.snapshot = None
        self.settings = {}
        self.status = tk.StringVar(value='Stopped. No screen capture or microphone activity.')
        self.capture_status = tk.StringVar(value='Capture: idle. Nothing captured.')
        self.folder_status = tk.StringVar(value='No folder selected. Nothing indexed or attached.')
        self.screenshot = tk.BooleanVar(value=True)
        self.use_context = tk.BooleanVar(value=False)
        self.speak_replies = tk.BooleanVar(value=True)
        self.voice = tk.StringVar(value=load_voice())
        outer = ttk.Frame(root, padding=12)
        outer.pack(fill='both', expand=True)
        # Reserve the composer/privacy area before allocating flexible transcript space.
        footer = ttk.Frame(outer)
        footer.pack(side='bottom', fill='x')
        ttk.Label(outer, text='Idiot Chat', font=('Helvetica', 20, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Watch and Chat shares your screen and microphone until you press Stop.').pack(anchor='w')
        settings = ttk.LabelFrame(outer, text='API settings (memory only; editable while stopped)', padding=8)
        settings.pack(fill='x', pady=(8, 6))
        self.settings_entries = []
        fields = [('base_url', 'API base URL', self.config.base_url),
                  ('model', 'Vision / chat model', self.config.model),
                  ('api_key', 'API key (optional for local APIs)', self.config.api_key),
                  ('transcription_model', 'Transcription model (optional voice)', self.config.transcription_model)]
        for row, (key, label, value) in enumerate(fields):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=2)
            variable = tk.StringVar(value=value)
            self.settings[key] = variable
            entry = ttk.Entry(settings, textvariable=variable, show='•' if key == 'api_key' else '')
            entry.grid(row=row, column=1, sticky='ew', pady=2)
            self.settings_entries.append(entry)
        ttk.Label(settings, text='Edge TTS voice').grid(row=4, column=0, sticky='w')
        voices = ttk.Combobox(settings, textvariable=self.voice, values=VOICES)
        voices.grid(row=4, column=1, sticky='ew')
        self.settings_entries.append(voices)
        settings.columnconfigure(1, weight=1)
        controls = ttk.Frame(outer)
        controls.pack(fill='x', pady=4)
        ttk.Style(root).configure('Watch.TButton', font=('Helvetica', 12, 'bold'), padding=8)
        self.start_button = ttk.Button(controls, text='Watch and Chat', command=self.start, style='Watch.TButton')
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(controls, text='Stop', command=self.stop)
        self.stop_button.pack(side='left', padx=5)
        self.clear_button = ttk.Button(controls, text='Clear chat', command=self.clear)
        self.clear_button.pack(side='left')
        ttk.Label(outer, textvariable=self.status, wraplength=930).pack(anchor='w', pady=3)
        ttk.Label(outer, textvariable=self.capture_status, wraplength=930).pack(anchor='w')
        attach = ttk.Frame(outer)
        attach.pack(fill='x', pady=5)
        ttk.Checkbutton(attach, text='Include screen in typed messages', variable=self.screenshot).pack(side='left')
        ttk.Checkbutton(attach, text='Attach selected folder text', variable=self.use_context).pack(side='left', padx=8)
        folder = ttk.Frame(outer)
        folder.pack(fill='x')
        self.folder_button = ttk.Button(folder, text='Choose / re-index folder…', command=self.choose_folder)
        self.folder_button.pack(side='left')
        self.preview_button = ttk.Button(folder, text='Review text to attach', command=self.preview_context)
        self.preview_button.pack(side='left', padx=5)
        self.remove_folder_button = ttk.Button(folder, text='Remove folder', command=self.remove_folder)
        self.remove_folder_button.pack(side='left')
        ttk.Label(outer, textvariable=self.folder_status, wraplength=930).pack(anchor='w', pady=(3, 5))
        self.transcript = ScrolledText(outer, height=13, wrap='word', state='disabled')
        self.transcript.pack(fill='both', expand=True)
        ttk.Label(footer, text='Question (Command+Return or Control+Return to send)').pack(anchor='w', pady=(6, 2))
        self.question = tk.Text(footer, height=3, wrap='word', undo=True)
        self.question.pack(fill='x')
        self.question.bind('<Command-Return>', self.send)
        self.question.bind('<Control-Return>', self.send)
        actions = ttk.Frame(footer)
        actions.pack(fill='x', pady=6)
        self.send_button = ttk.Button(actions, text='Send', command=self.send)
        self.send_button.pack(side='left')
        self.speech_check = ttk.Checkbutton(actions, text='Speak replies (Edge TTS)', variable=self.speak_replies)
        self.speech_check.pack(side='left', padx=8)
        ttk.Button(actions, text='Mute', command=self.mute).pack(side='left')
        if not self.speaker.available:
            self.speech_check.configure(state='disabled')
        self.privacy_label = ttk.Label(footer, text=(
            'Privacy: Send transmits your question, recent chat, and the attachments you enable to the API above. '
            'Screenshots may include private windows. Folder exclusions are not secret detection: review the text. '
            'Watch and Chat automatically sends screen frames and microphone speech until Stop. Chat is not saved. '
            'OS capture may use a temporary file. Providers may retain data or charge. Stop cannot recall a sent request.'
        ), wraplength=930, foreground='#555555')
        self.privacy_label.pack(anchor='w', pady=(2, 0))
        def resize_labels(event):
            for child in outer.winfo_children() + footer.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(wraplength=max(300, event.width - 8))
        outer.bind('<Configure>', resize_labels)
        self.refresh()
        self.poll_after = self.root.after(80, self.poll)

    def append(self, label, text):
        self.transcript.configure(state='normal')
        self.transcript.insert('end', '%s\n%s\n\n' % (label, text))
        self.transcript.see('end')
        self.transcript.configure(state='disabled')

    def notice(self, text):
        self.status.set(text)
        self.append('Notice', text)

    def refresh(self):
        active = self.session.active
        idle = active and not self.busy and not self.indexing
        self.start_button.configure(state='disabled' if active or self.busy else 'normal')
        self.stop_button.configure(state='normal' if active else 'disabled')
        self.send_button.configure(state='normal' if idle else 'disabled')
        self.clear_button.configure(state='disabled' if self.busy else 'normal')
        for button in (self.folder_button, self.remove_folder_button):
            button.configure(state='disabled' if self.busy or self.indexing or self.recorder.active else 'normal')
        self.preview_button.configure(state='normal' if self.snapshot else 'disabled')
        for entry in self.settings_entries:
            entry.configure(state='disabled' if active or self.busy else 'normal')

    def start(self):
        if self.session.active or self.busy:
            return
        try:
            self.config = replace(self.config, **{key: value.get().strip() for key, value in self.settings.items()})
        except ValueError as error:
            self.notice(str(error))
            return
        if self.config.base_url.rstrip('/') == 'https://api.openai.com/v1' and not self.config.api_key:
            self.notice('Enter an API key before Watch and Chat, or configure a local API URL.')
            return
        try:
            save_voice(self.voice.get().strip())
        except OSError:
            self.notice('Could not save voice preference. This session can still use it.')
        self.session.start()
        self.status.set('Listening… Speak naturally; Stop ends the session.')
        self.capture_status.set('Screen: ready. Captured automatically with each spoken turn.')
        self.append('Idiot Chat', 'What do you need help with?')
        self.speak('What do you need help with?')
        # Opening the input is quick; synthesis, transcription and model calls are workers.
        try:
            self.recorder.start()
        except VoiceError as error:
            self.notice(str(error) + ' Typed screen chat remains available.')
        self.refresh()
        self.watch_step()
        self.question.focus_set()

    def speak(self, text):
        if not self.speak_replies.get() or not self.session.active:
            return
        token, voice = self.session.token(), self.voice.get()
        def work():
            try:
                self.speaker.speak(text, voice, token)
            except Exception as error:
                message = str(error) if isinstance(error, VoiceError) else 'Speech failed. Replies remain visible.'
                self.events.put(('speech_error', token, message))
        threading.Thread(target=work, daemon=True).start()

    def interrupt(self):
        """Invalidate this turn before cancelling audio. Old workers can never publish."""
        self.session.start()
        self.speaker.stop()
        self.busy = False
        self.status.set('Listening…')
        self.refresh()

    def watch_step(self, initial=False):
        self.watch_after = None
        if not self.session.active or self.closed:
            return
        if self.recorder.active:
            if self.recorder.speech_started.is_set():
                self.recorder.speech_started.clear()
                self.interrupt()
            if self.recorder.ready() and not self.busy and not self.indexing:
                try:
                    audio = self.recorder.take()
                except VoiceError as error:
                    self.stop()
                    self.notice(str(error))
                    return
                if audio:
                    self.voice_turn(audio)
        self.watch_after = self.root.after(60, self.watch_step)

    def voice_turn(self, audio):
        token, config, history = self.session.token(), self.config, list(self.history)
        context = self.snapshot.text if self.use_context.get() and self.snapshot else ''
        self.status.set('Understanding your question… You can interrupt by speaking.')
        self.capture_status.set('Screen: captured automatically for each spoken turn.')
        def work():
            if token.is_set():
                return None
            frame = capture_screen()
            if token.is_set():
                return None
            question = Client(config).transcribe(audio).strip()
            if token.is_set() or not question:
                return None
            reply = Client(config).chat(build_messages(question, history, frame, context))
            return ('chat', question, reply)
        self.launch(token, work)

    def stop(self):
        if self.watch_after is not None:
            self.root.after_cancel(self.watch_after)
            self.watch_after = None
        was_busy = self.busy
        self.session.stop()
        self.busy = False
        self.recorder.cancel()
        self.speaker.stop()
        self.status.set('Stopped. Pending results discarded; an already-sent request cannot be recalled.'
                        if was_busy else 'Stopped. No screen capture or microphone activity.')
        self.capture_status.set('Capture: stopped. No further captures scheduled.')
        self.refresh()

    def clear(self):
        if self.busy:
            return
        self.history.clear()
        self.transcript.configure(state='normal')
        self.transcript.delete('1.0', 'end')
        self.transcript.configure(state='disabled')
        self.status.set('Chat cleared from memory.')

    def remove_folder(self):
        if self.busy or self.indexing or self.recorder.active:
            return
        self.snapshot = None
        self.use_context.set(False)
        self.folder_status.set('No folder selected. Nothing indexed or attached.')
        self.refresh()

    def choose_folder(self):
        if self.busy or self.indexing or self.recorder.active:
            return
        from tkinter import filedialog
        folder = filedialog.askdirectory(parent=self.root, title='Select text folder to review and attach')
        if not folder:
            return
        self.indexing = True
        self.folder_status.set('Indexing selected folder locally. Nothing sent.')
        self.refresh()

        def work():
            try:
                self.events.put(('folder', index_folder(folder), None))
            except Exception:
                self.events.put(('folder', None, 'Could not index folder. Check read permissions and try again.'))
        threading.Thread(target=work, daemon=True).start()

    def preview_context(self):
        if self.snapshot is None:
            return
        from tkinter.scrolledtext import ScrolledText
        window = self.tk.Toplevel(self.root)
        window.title('Exact folder text to attach (local preview)')
        window.geometry('800x600')
        text = ScrolledText(window, wrap='word')
        text.pack(fill='both', expand=True)
        text.insert('1.0', self.snapshot.text or '(No eligible text files.)')
        text.configure(state='disabled')

    def launch(self, token, work):
        self.busy = True
        self.refresh()

        def run():
            try:
                value = work()
                self.events.put(('done', token, value, None))
            except (APIError, CaptureError, VoiceError, ValueError) as error:
                self.events.put(('done', token, None, str(error)))
            except Exception:
                self.events.put(('done', token, None, 'The operation failed unexpectedly. '
                                 'Check configuration and permissions, then retry. No automatic retry was sent.'))
        threading.Thread(target=run, daemon=True).start()

    def send(self, event=None):
        if not self.session.active or self.busy or self.indexing:
            return 'break'
        question = self.question.get('1.0', 'end').strip()
        if not question or len(question) > 12000:
            self.notice('Enter a question of 1 to 12,000 characters.')
            return 'break'
        if self.use_context.get() and self.snapshot is None:
            self.notice('Choose and review a folder first, or untick folder context.')
            return 'break'
        self.interrupt()
        token = self.session.token()
        config = self.config
        history = list(self.history)
        context = self.snapshot.text if self.use_context.get() and self.snapshot else ''
        capture = self.screenshot.get()
        self.speaker.stop()
        self.status.set('Preparing one request. Stop discards its eventual result.')
        self.capture_status.set('Capture: taking ONE screenshot now…' if capture else 'Capture: disabled for this message.')

        def work():
            if token.is_set():
                return None
            screenshot = capture_screen() if capture else None
            if token.is_set():
                return None
            messages = build_messages(question, history, screenshot, context)
            if token.is_set():
                return None
            reply = Client(config).chat(messages)
            return ('chat', question, reply)
        self.launch(token, work)
        return 'break'

    def mute(self):
        self.speak_replies.set(False)
        self.speaker.stop()

    def poll(self):
        if self.closed:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == 'folder':
                self.indexing = False
                snapshot, error = event[1:]
                if error:
                    self.folder_status.set(error + ' Previous selection unchanged.')
                else:
                    self.snapshot = snapshot
                    self.use_context.set(False)
                    self.folder_status.set('%s files, %s chars; %s skipped%s. Review, then tick Attach selected folder text.' % (
                        len(snapshot.files), len(snapshot.text), snapshot.skipped,
                        '; LIMITED / TRUNCATED' if snapshot.truncated else ''))
                self.refresh()
            elif kind == 'speech_error':
                if self.session.current(event[1]):
                    self.notice(event[2])
            elif kind == 'done':
                token, value, error = event[1:]
                if self.session.current(token):
                    self.busy = False
                    if error:
                        self.stop()
                        self.notice(error + ' Capture stopped. Fix the issue, then press Watch and Chat.')
                    elif value is not None and value[0] == 'chat':
                        _, question, reply = value
                        self.history.extend([('user', question), ('assistant', reply)])
                        self.history[:] = self.history[-40:]
                        self.append('You', question)
                        self.append('Idiot Chat', reply)
                        # Preserve edits typed while the request was in flight.
                        if self.question.get('1.0', 'end').strip() == question:
                            self.question.delete('1.0', 'end')
                        self.status.set('WATCHING' + (' + MICROPHONE LIVE' if self.recorder.active else ' (microphone unavailable)') + '. Stop ends capture.')
                        if self.speak_replies.get():
                            try:
                                self.speak(reply)
                            except VoiceError as voice_error:
                                self.notice(str(voice_error))
                elif not self.session.active:
                    self.status.set('Stopped. Pending result discarded. No capture or microphone activity.')
                self.refresh()
        self.poll_after = self.root.after(80, self.poll)

    def close(self):
        self.closed = True
        self.root.after_cancel(self.poll_after)
        self.stop()
        self.history.clear()
        self.snapshot = None
        for variable in self.settings.values():
            variable.set('')
        self.root.destroy()


def main():
    try:
        import tkinter as tk
    except ImportError:
        raise SystemExit('Tkinter is missing. Install Python from python.org (includes Tk on macOS), '
                         'or install the matching python-tk package for your Python version.')
    try:
        config = Config.from_env()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    try:
        root = tk.Tk()
    except tk.TclError:
        raise SystemExit('Could not open a desktop window. Run from a logged-in graphical session '
                         'with a working Tk installation. On macOS, use Python from python.org.') from None
    App(root, config)
    root.mainloop()


if __name__ == '__main__':
    main()
