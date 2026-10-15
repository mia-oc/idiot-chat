"""Opt-in desktop integration tests. Use a local API and synthetic image, never real capture."""
import io
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch, Mock

from idiot_chat.capture import CaptureError
from idiot_chat.config import Config
from idiot_chat.voice import VoiceError


@unittest.skipUnless(os.environ.get('IDIOT_CHAT_GUI_TESTS') == '1', 'requires an opted-in desktop Tk session')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from PIL import Image
        from idiot_chat.app import App
        self.requests = []
        self.request_started = threading.Event()
        self.release_request = threading.Event()
        self.release_request.set()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((self.path, body))
                owner.request_started.set()
                owner.release_request.wait(5)
                data = json.dumps({'choices': [{'message': {'content': 'A local mock reply'}}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.recorder_patch = patch('idiot_chat.app.Recorder')
        self.recorder = self.recorder_patch.start().return_value
        self.recorder.active = False
        self.recorder.start.side_effect = lambda: setattr(self.recorder, 'active', True)
        self.recorder.cancel.side_effect = lambda: setattr(self.recorder, 'active', False)
        self.recorder.take.return_value = None
        self.app = App(self.root, Config(base_url='http://127.0.0.1:%s/v1' % self.server.server_port))
        image = io.BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(image, format='PNG')
        self.capture_patch = patch('idiot_chat.app.capture_screen', return_value=image.getvalue())
        self.capture = self.capture_patch.start()

    def tearDown(self):
        self.release_request.set()
        self.app.close()
        self.capture_patch.stop()
        self.recorder_patch.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def drain(self):
        deadline = time.monotonic() + 5
        while self.app.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.root.update()
        self.assertFalse(self.app.busy, 'worker did not finish')

    def test_privacy_note_and_send_controls_remain_visible_at_minimum_size(self):
        self.root.deiconify()
        self.root.geometry('760x700')
        self.root.update()
        for widget in (self.app.privacy_label, self.app.send_button, self.app.start_button, self.app.stop_button):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
        self.capture.assert_not_called()
        self.assertEqual(self.requests, [])

    def test_watch_starts_screen_and_voice_then_repeats_and_stops(self):
        self.app.send()
        self.capture.assert_not_called()
        self.recorder.start.assert_not_called()
        self.app.start()
        self.drain()
        self.capture.assert_called_once()
        self.recorder.start.assert_called_once()
        content = self.requests[0][1]['messages'][-1]['content']
        self.assertTrue(content[1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.recorder.take.return_value = b'synthetic wav'
        self.root.after_cancel(self.app.watch_after)
        with patch('idiot_chat.app.Client.transcribe', return_value='What is on my screen?') as transcribe:
            self.app.watch_step()
            self.drain()
            transcribe.assert_called_once_with(b'synthetic wav')
        self.assertIn('What is on my screen?', str(self.requests[-1]))
        self.assertEqual(self.capture.call_count, 2)
        self.app.stop()
        self.assertFalse(self.recorder.active)
        self.assertIsNone(self.app.watch_after)
        self.app.watch_step()
        self.assertEqual(self.capture.call_count, 2)

    def test_stop_discards_pending_response(self):
        self.release_request.clear()
        self.app.start()
        self.app.question.insert('1.0', 'Pending question')
        self.assertTrue(self.request_started.wait(3))
        self.app.stop()
        self.release_request.set()
        self.drain()
        self.assertEqual(self.app.history, [])
        self.assertEqual(self.app.question.get('1.0', 'end').strip(), 'Pending question')
        self.assertIn('discarded', self.app.status.get())

    def test_capture_error_sends_nothing_and_preserves_draft(self):
        self.capture.side_effect = CaptureError('Screen Recording permission required')
        self.app.start()
        self.app.question.insert('1.0', 'My question')
        self.drain()
        self.assertEqual(self.requests, [])
        self.assertIn('Screen Recording', self.app.status.get())
        self.assertEqual(self.app.question.get('1.0', 'end').strip(), 'My question')

    def test_voice_unavailable_leaves_screen_chat_working(self):
        self.recorder.start.side_effect = VoiceError('Microphone unavailable')
        self.app.start()
        self.drain()
        self.assertFalse(self.app.recorder.active)
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.app.session.active)

    def test_missing_key_never_starts_capture(self):
        self.app.settings['base_url'].set('https://api.openai.com/v1')
        self.app.start()
        self.capture.assert_not_called()
        self.recorder.start.assert_not_called()
        self.assertFalse(self.app.session.active)


if __name__ == '__main__':
    unittest.main()
