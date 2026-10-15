"""Session gate shared by GUI and worker threads. Stop invalidates pending results."""
import threading


class Session:
    def __init__(self):
        self._lock = threading.Lock()
        self._token = None

    @property
    def active(self):
        with self._lock:
            return self._token is not None and not self._token.is_set()

    def start(self):
        with self._lock:
            if self._token is not None:
                self._token.set()
            self._token = threading.Event()
            return self._token

    def stop(self):
        with self._lock:
            if self._token is not None:
                self._token.set()
            self._token = None

    def token(self):
        with self._lock:
            if self._token is None or self._token.is_set():
                raise RuntimeError('Start a session first.')
            return self._token

    def current(self, token):
        with self._lock:
            return token is self._token and not token.is_set()
