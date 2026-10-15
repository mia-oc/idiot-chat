"""Bounded live microphone buffering and macOS speech. No microphone at import/startup."""
import io
import tempfile
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import wave


class VoiceError(RuntimeError):
    pass


class Recorder:
    MAX_SECONDS = 30
    SAMPLE_RATE = 16000

    def __init__(self):
        self.stream = None
        self._chunks = []
        self._frames = 0
        self._lock = threading.Lock()
        self.started_at = 0.0
        self.overflowed = False
        self.speech_started = threading.Event()
        self.speech_active = False
        self.last_voice = 0.0

    @property
    def active(self):
        return self.stream is not None

    def start(self):
        if self.active:
            raise VoiceError('A recording is already active.')
        try:
            import sounddevice as sd
        except (ImportError, OSError):
            raise VoiceError('Microphone support is missing. Install idiot-chat[voice] and PortAudio '
                             '(brew install portaudio), or keep using typed chat.') from None
        self._chunks = []
        self._frames = 0
        self.speech_active = False
        self.speech_started.clear()
        self.overflowed = False
        limit = self.SAMPLE_RATE * self.MAX_SECONDS

        def callback(indata, frames, timing, status):
            from array import array
            samples = array('h', bytes(indata))
            loud = bool(samples) and sum(v*v for v in samples) / len(samples) > 500 ** 2
            now = time.monotonic()
            if loud:
                if not self.speech_active:
                    self.speech_active = True
                    self.speech_started.set()
                self.last_voice = now
            if not self.speech_active:
                return
            with self._lock:
                remaining = limit - self._frames
                take = min(frames, max(0, remaining))
                if take:
                    self._chunks.append(bytes(indata[:take]))
                    self._frames += take
                if status:
                    self.overflowed = True
                if self._frames >= limit:
                    pass  # Bound pending audio to 30 seconds until the next live turn.

        try:
            self.stream = sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1,
                                         dtype='int16', callback=callback)
            self.started_at = time.monotonic()
            self.stream.start()
        except Exception:
            self.cancel()
            raise VoiceError('Could not open the microphone. On macOS allow the launching terminal '
                             'or Python app in System Settings > Privacy & Security > Microphone, '
                             'then restart it. Check the default input device. Typed chat still works.') from None

    def ready(self):
        return self.speech_active and (time.monotonic() - self.last_voice > 0.7 or
                                      self._frames >= self.SAMPLE_RATE * self.MAX_SECONDS)

    def take(self):
        """Drain a bounded live chunk without closing the input stream; ignore silence."""
        self.speech_active = False
        from array import array
        with self._lock:
            data = b''.join(self._chunks)
            self._chunks.clear()
            self._frames = 0
            overflowed, self.overflowed = self.overflowed, False
        if overflowed:
            raise VoiceError('The microphone dropped audio. Check the input device and restart Watch and Chat.')
        samples = array('h', data)
        if not samples or sum(v * v for v in samples) / len(samples) < 200 ** 2:
            return None
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.SAMPLE_RATE)
            wav.writeframes(data)
        return output.getvalue()

    def finish(self):
        if self.stream is None:
            raise VoiceError('No recording is active.')
        self._close()
        with self._lock:
            data = b''.join(self._chunks)
            self._chunks.clear()
        if not data:
            raise VoiceError('No audio was recorded. Try again or type your question.')
        if self.overflowed:
            raise VoiceError('The microphone dropped audio. Please retry or use typed chat.')
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.SAMPLE_RATE)
            wav.writeframes(data)
        return output.getvalue()

    def _close(self):
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.abort()
            finally:
                stream.close()

    def cancel(self):
        try:
            self._close()
        except Exception:
            pass
        with self._lock:
            self._chunks.clear()


DEFAULT_VOICE = 'en-GB-SoniaNeural'
VOICES = (DEFAULT_VOICE, 'en-GB-RyanNeural', 'en-US-JennyNeural', 'en-US-GuyNeural')


class Speaker:
    """Replaceable speak(text, voice, cancel)/stop provider. No Tk calls here."""
    def __init__(self):
        self.process = None
        self._lock = threading.Lock()

    @property
    def available(self):
        return True  # Missing dependencies produce a useful text-only error at invocation.

    def _run(self, command, cancel):
        with self._lock:
            if cancel.is_set():
                return False
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.process = process
        try:
            while process.poll() is None:
                if cancel.wait(0.03):
                    process.terminate()
                    try:
                        process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return False
            if process.returncode and not cancel.is_set():
                raise VoiceError('Edge speech failed. Check internet access and install idiot-chat[voice]. Replies remain visible.')
            return not cancel.is_set()
        finally:
            process.wait()
            with self._lock:
                if self.process is process:
                    self.process = None

    def speak(self, text, voice=DEFAULT_VOICE, cancel=None):
        cancel = cancel or threading.Event()
        player = ['/usr/bin/afplay'] if sys.platform == 'darwin' else ([shutil.which('ffplay'), '-nodisp', '-autoexit'] if shutil.which('ffplay') else None)
        if player is None:
            raise VoiceError('Install ffplay for speech playback on this platform. Replies remain visible.')
        try:
            with tempfile.TemporaryDirectory(prefix='idiot-chat-tts-') as directory:
                output = str(Path(directory) / 'speech.mp3')
                if self._run([sys.executable, '-m', 'edge_tts', '--voice', voice,
                              '--text', text[:12000], '--write-media', output], cancel):
                    self._run(player + [output], cancel)
        except OSError:
            raise VoiceError('Speech playback could not start. Replies remain visible.') from None

    def stop(self):
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
