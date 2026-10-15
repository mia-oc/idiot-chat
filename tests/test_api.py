import base64
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from idiot_chat.api import APIError, Client, build_messages, build_request, endpoint
from idiot_chat.config import Config


class RequestTests(unittest.TestCase):
    def test_current_image_context_and_history_are_constructed(self):
        messages = build_messages('What is this?', [('user', 'Earlier'), ('assistant', 'Reply')],
                                  b'png-bytes', 'notes.md: useful')
        self.assertEqual([m['role'] for m in messages], ['system', 'user', 'assistant', 'user'])
        content = messages[-1]['content']
        self.assertIn('What is this?', content[0]['text'])
        self.assertIn('notes.md: useful', content[0]['text'])
        self.assertEqual(content[1]['image_url']['url'],
                         'data:image/png;base64,' + base64.b64encode(b'png-bytes').decode())
        self.assertNotIn('notes.md', messages[1]['content'])

    def test_text_only_and_bounded_complete_history_pairs(self):
        messages = build_messages('Now', [('user', 'A' * 80), ('assistant', 'B' * 80),
                                         ('user', 'Recent'), ('assistant', 'Answer')],
                                  history_chars=40)
        self.assertEqual(messages[1:-1], [{'role': 'user', 'content': 'Recent'},
                                        {'role': 'assistant', 'content': 'Answer'}])
        self.assertEqual(messages[-1]['content'], 'Now')

    def test_request_uses_configured_endpoint_auth_and_model(self):
        config = Config(base_url='http://localhost:1234/v1/', model='local-vision', api_key='test-key')
        request = build_request(config, build_messages('Hello'))
        self.assertEqual(request.full_url, 'http://localhost:1234/v1/chat/completions')
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-key')
        body = json.loads(request.data)
        self.assertEqual(body['model'], 'local-vision')
        self.assertFalse(body['stream'])
        self.assertEqual(body['max_tokens'], config.max_tokens)

    def test_optional_key_and_endpoint_validation(self):
        request = build_request(Config(api_key=''), build_messages('Hi'))
        self.assertIsNone(request.get_header('Authorization'))
        for url in ('ftp://host/v1', 'https://user:password@host/v1', 'https://host/v1?key=secret', ''):
            with self.assertRaises(ValueError):
                endpoint(url, 'chat/completions')

    def test_errors_never_echo_provider_body_or_key(self):
        client = Client(Config(api_key='private-key'))
        error = HTTPError('https://example.com', 401, 'private-key', {}, io.BytesIO(b'private-key'))
        with patch('idiot_chat.api.urlopen', side_effect=error):
            with self.assertRaisesRegex(APIError, '401') as raised:
                client.chat(build_messages('Hello'))
        self.assertNotIn('private-key', str(raised.exception))

    def test_voice_request_uses_same_root_and_multipart_audio(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"text": "A spoken question"}'
        client = Client(Config(base_url='http://localhost:1234/v1', transcription_model='local-whisper'))
        with patch('idiot_chat.api.urlopen', return_value=response) as send:
            self.assertEqual(client.transcribe(b'RIFF-audio'), 'A spoken question')
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'http://localhost:1234/v1/audio/transcriptions')
        self.assertIn('multipart/form-data', request.get_header('Content-type'))
        self.assertIn(b'local-whisper', request.data)
        self.assertIn(b'filename="recording.wav"', request.data)
        self.assertIn(b'RIFF-audio', request.data)

    def test_network_and_invalid_responses_are_actionable(self):
        client = Client(Config())
        with patch('idiot_chat.api.urlopen', side_effect=URLError('sensitive-url')):
            with self.assertRaisesRegex(APIError, 'connect'):
                client.chat(build_messages('Hello'))
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"choices": []}'
        with patch('idiot_chat.api.urlopen', return_value=response):
            with self.assertRaisesRegex(APIError, 'response'):
                client.chat(build_messages('Hello'))


if __name__ == '__main__':
    unittest.main()
