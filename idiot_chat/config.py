"""API configuration stays in memory; only the non-secret voice preference is saved."""
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


def validate_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
        raise ValueError('API base URL must be http(s), without credentials, query or fragment.')
    try:
        parsed.port
    except ValueError:
        raise ValueError('API base URL has an invalid port.') from None
    return value.rstrip('/')


@dataclass(frozen=True)
class Config:
    base_url: str = 'https://api.openai.com/v1'
    api_key: str = field(default='', repr=False)
    model: str = 'gpt-4o-mini'
    transcription_model: str = 'whisper-1'
    timeout: float = 60.0
    max_tokens: int = 1200

    def __post_init__(self):
        validate_url(self.base_url)
        if not self.model.strip() or not self.transcription_model.strip():
            raise ValueError('Model names cannot be empty.')
        if not 1 <= self.timeout <= 180:
            raise ValueError('Timeout must be between 1 and 180 seconds.')
        if not 1 <= self.max_tokens <= 16384:
            raise ValueError('Maximum reply tokens must be between 1 and 16384.')
        if '\r' in self.api_key or '\n' in self.api_key:
            raise ValueError('API key must be a single line.')

    @classmethod
    def from_env(cls):
        try:
            return cls(
                base_url=os.environ.get('IDIOT_CHAT_BASE_URL', cls.base_url),
                api_key=os.environ.get('IDIOT_CHAT_API_KEY', os.environ.get('OPENAI_API_KEY', '')),
                model=os.environ.get('IDIOT_CHAT_MODEL', cls.model),
                transcription_model=os.environ.get('IDIOT_CHAT_TRANSCRIPTION_MODEL', cls.transcription_model),
                timeout=float(os.environ.get('IDIOT_CHAT_TIMEOUT', '60')),
                max_tokens=int(os.environ.get('IDIOT_CHAT_MAX_TOKENS', '1200')),
            )
        except (TypeError, ValueError) as error:
            raise ValueError('Invalid configuration: %s' % error) from None


# Only the non-secret voice preference is persisted. API credentials remain in memory.
def settings_path():
    from pathlib import Path
    return Path(os.environ.get('IDIOT_CHAT_SETTINGS', str(Path.home() / '.config/idiot-chat/settings.json')))


def load_voice():
    import json
    from .voice import DEFAULT_VOICE
    try:
        value = json.loads(settings_path().read_text()).get('voice')
        return value if isinstance(value, str) and value.strip() else DEFAULT_VOICE
    except (OSError, ValueError, TypeError, AttributeError):
        return DEFAULT_VOICE


def save_voice(voice):
    import json
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'voice': voice}))
    temporary.replace(path)
