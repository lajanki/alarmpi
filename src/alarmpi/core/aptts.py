import subprocess
import tempfile

import pydub.playback


class AlarmpiTTS:
    """Base class for TTS clients. Provide a common credentials argument
    and an abstract method for initializing the actual TTS client.
    """

    def __init__(self, auth: dict | None = None, config: dict | None = None):
        self.auth = auth
        self.config = config or {}
        self._playback_process = None

    def setup(self, text):
        """Set up a TTS client and convert text to audio.
        Args:
            text (string): text to be processed by the TTS client.
        Return:
            Audio content to be played as pydub.AudioSegment
        """
        raise NotImplementedError

    def play(self, audio):
        """Play audio content.
        Args:
            audio (pydub.AudioSegment): prebuilt content to be played
        """
        # pydub.play() hides its process. Launch the selected player ourselves
        # with a temporary WAV so stop() can terminate it during shutdown.
        player = pydub.playback.get_player_name()
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio.export(audio_file.name, format="wav")
            process = subprocess.Popen(
                [
                    player,
                    "-nodisp",
                    "-autoexit",
                    "-hide_banner",
                    audio_file.name,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._playback_process = process
            try:
                process.wait()
            finally:
                if self._playback_process is process:
                    self._playback_process = None

    def stop(self):
        """Stop any currently playing TTS audio."""
        process = self._playback_process
        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
