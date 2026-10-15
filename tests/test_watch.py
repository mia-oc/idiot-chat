"""Live flow wiring with synthetic devices, no GUI or network required."""
import queue
import unittest
from unittest.mock import Mock, patch

from idiot_chat.app import App
from idiot_chat.config import Config
from idiot_chat.session import Session
from idiot_chat.voice import Recorder, VoiceError


class WatchTests(unittest.TestCase):
    def make_app(self):
        app = App.__new__(App)
        app.root = Mock()
        app.session = Session()
        app.config = Config(base_url='http://localhost:1234/v1')
        app.settings = {}
        app.closed = app.busy = app.indexing = False
        app.watch_after = None
        app.history = []
        app.snapshot = None
        app.events = queue.Queue()
        app.recorder = Mock(active=False)
        app.recorder.start.side_effect = lambda: setattr(app.recorder, 'active', True)
        app.recorder.cancel.side_effect = lambda: setattr(app.recorder, 'active', False)
        app.recorder.take.return_value = b'wav'
        for name in ('speaker', 'status', 'capture_status', 'question', 'use_context', 'refresh', 'notice', 'append', 'voice', 'speak_replies'):
            setattr(app, name, Mock())
        app.voice.get.return_value = 'en-GB-SoniaNeural'
        app.recorder.speech_started = __import__('threading').Event()
        app.recorder.ready.return_value = False
        app.speak = Mock()
        app.launch = lambda token, work: app.events.put(work())
        return app

    @patch('idiot_chat.app.capture_screen', return_value=b'png')
    @patch('idiot_chat.app.Client')
    def test_one_click_wires_audio_screen_and_history_and_stop(self, client, capture):
        app = self.make_app()
        client.return_value.transcribe.return_value = 'Help me with this'
        client.return_value.chat.return_value = 'Hello'
        app.watch_step()
        capture.assert_not_called()
        app.recorder.start.assert_not_called()
        with patch('idiot_chat.app.save_voice'):
            app.start()
        app.speak.assert_called_once_with('What do you need help with?')
        capture.assert_not_called()
        app.recorder.speech_started.set()
        app.recorder.ready.return_value = True
        app.watch_step()
        app.recorder.start.assert_called_once()
        client.return_value.transcribe.assert_called_once_with(b'wav')
        messages = client.return_value.chat.call_args.args[0]
        self.assertIn('Help me with this', str(messages))
        self.assertIn('data:image/png;base64,', str(messages))
        capture.assert_called_once()
        self.assertEqual(app.events.get(), ('chat', 'Help me with this', 'Hello'))
        token = app.session.token()
        app.stop()
        self.assertTrue(token.is_set())
        self.assertFalse(app.recorder.active)
        app.root.after_cancel.assert_called_once()
        app.watch_step()
        capture.assert_called_once()

    @patch('idiot_chat.app.capture_screen')
    def test_missing_api_configuration_opens_no_devices(self, capture):
        app = self.make_app()
        app.config = Config()
        app.start()
        app.recorder.start.assert_not_called()
        capture.assert_not_called()
        self.assertFalse(app.session.active)

    def test_busy_turn_does_not_capture_or_drain_audio(self):
        app = self.make_app()
        app.session.start()
        app.busy = True
        app.watch_step()
        app.recorder.take.assert_not_called()
        app.root.after.assert_called_once_with(60, app.watch_step)

    def test_live_audio_is_drained_bounded_and_silence_ignored(self):
        recorder = Recorder()
        recorder._chunks = [b'\0\0' * 100]
        self.assertIsNone(recorder.take())
        self.assertEqual(recorder._chunks, [])
        recorder._chunks = [b'\xff\x7f' * 100]
        self.assertTrue(recorder.take().startswith(b'RIFF'))
        self.assertEqual(recorder._frames, 0)
        recorder.overflowed = True
        with self.assertRaises(VoiceError):
            recorder.take()


class CancellationTests(unittest.TestCase):
    make_app = WatchTests.make_app
    def test_barge_in_invalidates_reply_and_stops_audio(self):
        app = self.make_app()
        old = app.session.start()
        app.busy = True
        app.recorder.active = True
        app.recorder.speech_started.set()
        app.watch_step()
        self.assertTrue(old.is_set())
        self.assertTrue(app.session.active)
        self.assertFalse(app.busy)
        app.speaker.stop.assert_called_once()

    def test_late_response_cannot_clear_new_busy_or_speak(self):
        app = self.make_app()
        old = app.session.start()
        app.interrupt()
        app.busy = True
        app.events.put(('done', old, ('chat', 'old', 'stale'), None))
        app.poll()
        self.assertTrue(app.busy)
        self.assertEqual(app.history, [])
        app.speak.assert_not_called()

    def test_stop_releases_and_invalidates(self):
        app = self.make_app()
        old = app.session.start()
        app.watch_after = 'timer'
        app.stop()
        self.assertTrue(old.is_set())
        app.recorder.cancel.assert_called_once()
        app.speaker.stop.assert_called_once()
        self.assertIsNone(app.watch_after)

    def test_tts_invocation_and_error_are_worker_events(self):
        app = self.make_app()
        app.session.start()
        app.speaker.speak.side_effect = VoiceError('text fallback')
        import threading
        with patch('idiot_chat.app.threading.Thread') as thread:
            thread.side_effect = lambda target, daemon: Mock(start=target)
            App.speak(app, 'hello')
        app.speaker.speak.assert_called_once_with('hello', 'en-GB-SoniaNeural', app.session.token())
        self.assertEqual(app.events.get()[0], 'speech_error')

    def test_voice_preference_persists_without_credentials(self):
        import tempfile, os, json
        from pathlib import Path
        from idiot_chat.config import save_voice, load_voice
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            with patch.dict(os.environ, {'IDIOT_CHAT_SETTINGS': str(path)}):
                save_voice('en-GB-RyanNeural')
                self.assertEqual(load_voice(), 'en-GB-RyanNeural')
                self.assertEqual(json.loads(path.read_text()), {'voice': 'en-GB-RyanNeural'})
