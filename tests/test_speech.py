"""Provider lifecycle uses fake processes, never network or physical speakers."""
import threading
import unittest
from unittest.mock import Mock, patch

from idiot_chat.voice import Speaker, DEFAULT_VOICE


class SpeechTests(unittest.TestCase):
    @patch('idiot_chat.voice.sys.platform', 'darwin')
    def test_edge_synthesis_then_platform_playback(self):
        speaker = Speaker()
        with patch.object(speaker, '_run', return_value=True) as run:
            speaker.speak('Welcome', DEFAULT_VOICE, threading.Event())
        self.assertIn('edge_tts', run.call_args_list[0].args[0])
        self.assertIn(DEFAULT_VOICE, run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[1].args[0][0], '/usr/bin/afplay')

    @patch('idiot_chat.voice.subprocess.Popen')
    def test_cancelled_before_synthesis_opens_no_process(self, popen):
        cancel = threading.Event()
        cancel.set()
        self.assertFalse(Speaker()._run(['fake'], cancel))
        popen.assert_not_called()

    @patch('idiot_chat.voice.subprocess.Popen')
    def test_cancel_inflight_terminates_and_reaps(self, popen):
        cancel = Mock()
        cancel.is_set.return_value = False
        cancel.wait.return_value = True
        process = popen.return_value
        process.poll.return_value = None
        speaker = Speaker()
        self.assertFalse(speaker._run(['fake'], cancel))
        process.terminate.assert_called_once()
        self.assertTrue(process.wait.called)
        self.assertIsNone(speaker.process)

class DetectorTests(unittest.TestCase):
    def test_speech_onset_silence_endpoint_and_stop_close_stream(self):
        from array import array
        import sys
        from idiot_chat.voice import Recorder
        device = Mock()
        with patch.dict(sys.modules, {'sounddevice': device}):
            recorder = Recorder()
            recorder.start()
            callback = device.InputStream.call_args.kwargs['callback']
            callback(array('h', [0]*160), 160, None, False)
            self.assertEqual(recorder._frames, 0)
            callback(array('h', [2000]*160), 160, None, False)
            self.assertTrue(recorder.speech_started.is_set())
            with patch('idiot_chat.voice.time.monotonic', return_value=recorder.last_voice + 0.8):
                self.assertTrue(recorder.ready())
            self.assertTrue(recorder.take().startswith(b'RIFF'))
            self.assertFalse(recorder.speech_active)
            recorder.cancel()
        device.InputStream.return_value.abort.assert_called_once()
        device.InputStream.return_value.close.assert_called_once()
        self.assertFalse(recorder.active)
