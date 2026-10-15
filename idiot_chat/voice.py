"""Optional bounded recording and macOS local speech. No microphone at import/startup."""
import io
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

    @property
    def active(self):
        return self.stream is not None

    def start(self):
        if self.active:
            raise VoiceError('A recording is already active.')
        try:
            import sounddevice as sd
        except (ImportError, OSError):
            raise VoiceError('Voice input is optional. Install idiot-chat[voice] and PortAudio '
                             '(brew install portaudio), or keep using typed chat.') from None
        self._chunks = []
        self._frames = 0
        self.overflowed = False
        limit = self.SAMPLE_RATE * self.MAX_SECONDS

        def callback(indata, frames, timing, status):
            with self._lock:
                remaining = limit - self._frames
                take = min(frames, max(0, remaining))
                if take:
                    self._chunks.append(bytes(indata[:take]))
                    self._frames += take
                if status:
                    self.overflowed = True
                if self._frames >= limit:
                    raise sd.CallbackStop()

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


class Speaker:
    def __init__(self):
        self.process = None

    @property
    def available(self):
        return sys.platform == 'darwin' and shutil.which('say') is not None

    def speak(self, text):
        self.stop()
        if not self.available:
            raise VoiceError('Speech output needs macOS /usr/bin/say. Replies remain visible as text.')
        try:
            # Use stdin rather than shell interpolation or command-line speech text.
            self.process = subprocess.Popen(['/usr/bin/say', '-f', '-'], stdin=subprocess.PIPE,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.process.communicate(text[:12000].encode('utf-8'), timeout=0.05)
        except subprocess.TimeoutExpired:
            pass  # say continues speaking; Stop or Mute terminates it.
        except OSError:
            raise VoiceError('Speech playback could not start. Replies remain visible as text.') from None

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=0.5)
            self.process = None
