"""Opt-in desktop integration tests. Use a local API and synthetic image, never real capture."""
import io
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

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
        self.app = App(self.root, Config(base_url='http://127.0.0.1:%s/v1' % self.server.server_port))
        image = io.BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(image, format='PNG')
        self.capture_patch = patch('idiot_chat.app.capture_screen', return_value=image.getvalue())
        self.capture = self.capture_patch.start()

    def tearDown(self):
        self.release_request.set()
        self.app.close()
        self.capture_patch.stop()
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
        for widget in (self.app.privacy_label, self.app.send_button, self.app.record_button):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
        self.capture.assert_not_called()
        self.assertEqual(self.requests, [])

    def test_explicit_start_screenshot_send_history_and_text_only(self):
        self.app.question.insert('1.0', 'Describe this')
        self.app.send()
        self.capture.assert_not_called()
        self.assertEqual(self.requests, [])
        self.app.start()
        self.capture.assert_not_called()
        self.app.send()
        self.drain()
        self.capture.assert_called_once()
        self.assertEqual(self.requests[0][0], '/v1/chat/completions')
        content = self.requests[0][1]['messages'][-1]['content']
        self.assertTrue(content[1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertEqual(self.app.history[-1], ('assistant', 'A local mock reply'))
        self.app.screenshot.set(False)
        self.app.question.insert('1.0', 'Follow-up')
        self.app.send()
        self.drain()
        self.capture.assert_called_once()
        self.assertEqual(len(self.requests[-1][1]['messages']), 4)
        self.assertEqual(self.requests[-1][1]['messages'][-1]['content'], 'Follow-up')
        self.app.stop()
        self.app.send()
        self.assertEqual(len(self.requests), 2)

    def test_stop_discards_pending_response(self):
        self.release_request.clear()
        self.app.start()
        self.app.question.insert('1.0', 'Pending question')
        self.app.send()
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
        self.app.send()
        self.drain()
        self.assertEqual(self.requests, [])
        self.assertIn('Screen Recording', self.app.status.get())
        self.assertEqual(self.app.question.get('1.0', 'end').strip(), 'My question')

    def test_voice_unavailable_leaves_typed_chat_working(self):
        self.app.start()
        with patch.object(self.app.recorder, 'start', side_effect=VoiceError('Microphone unavailable')):
            self.app.record()
        self.assertFalse(self.app.recorder.active)
        self.assertIn('Microphone unavailable', self.app.status.get())
        self.app.screenshot.set(False)
        self.app.question.insert('1.0', 'Typed fallback')
        self.app.send()
        self.drain()
        self.assertEqual(len(self.requests), 1)


if __name__ == '__main__':
    unittest.main()
