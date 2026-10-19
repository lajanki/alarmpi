import io
import wave

import pydub
from piper import PiperVoice

from alarmpi.core import aptts


class PiperTTSManager(aptts.AlarmpiTTS):
    def __init__(self, auth: dict | None = None, config: dict | None = None):
        super().__init__(auth=auth, config=config)
        model_path = self.config.get("model_path")
        if not model_path:
            raise ValueError("Piper TTS requires a model_path in its configuration")
        self.voice = PiperVoice.load(model_path)

    def setup(self, text):
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file)

        wav_buffer.seek(0)
        return pydub.AudioSegment.from_wav(wav_buffer)