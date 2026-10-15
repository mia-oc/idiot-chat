import os
import unittest
from unittest.mock import patch

from idiot_chat.config import Config


class ConfigTests(unittest.TestCase):
    def test_environment_and_openai_fallback(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fallback', 'IDIOT_CHAT_MODEL': 'local'}, clear=True):
            config = Config.from_env()
            self.assertEqual(config.api_key, 'fallback')
            self.assertEqual(config.model, 'local')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fallback', 'IDIOT_CHAT_API_KEY': 'explicit'}, clear=True):
            self.assertEqual(Config.from_env().api_key, 'explicit')

    def test_key_is_not_in_repr_and_invalid_settings_are_rejected(self):
        self.assertNotIn('private-key', repr(Config(api_key='private-key')))
        for values in ({'timeout': float('nan')}, {'timeout': 0}, {'max_tokens': 0},
                       {'model': ''}, {'api_key': 'bad\nkey'}, {'base_url': 'https://user:pass@host'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Config(**values)


if __name__ == '__main__':
    unittest.main()
