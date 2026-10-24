import glob
import logging
import os
import random
import subprocess
from threading import Event

import pydub
from PyQt5.QtCore import QThread, pyqtSignal

from alarmpi.core import aptts
from alarmpi.utils import utils
from alarmpi.handlers import get_handler, get_greeting


event_logger = logging.getLogger("eventLogger")


class AlarmBuilder:

    def __init__(self, config):
        self.media_play_thread = MediaPlayWorker()
        self.config = config
        self.audio = None
        self.audio_segments = []
        self.audio_player = aptts.AlarmpiTTS()
        self._playback_cancelled = Event()

    def build(self):
        """Build an alarm.

        Loop through the configuration file for enabled content sections
        and generate matching content.
        """
        self.audio = None
        self.audio_segments = []
        self.tts_client = None
        self._playback_cancelled.clear()

        # Initialize content with greeting
        contents = [("greeting", self.generate_greeting())]

        # For each content section get the handler module and create the approriate
        # content parser
        content_sections = self.config.get_enabled_sections("content")
        for section in content_sections:
            section_data = content_sections[section]
            if "text" in section_data:
                contents.append((section, section_data["text"]))
                continue

            class_ = get_handler("content", section.lower())
            parser = class_(section_data)

            # build content
            parser.build()
            contents.append((section, parser.get()))

        for _, text in contents:
            print(text)

        if self.config["media"]["enabled"]:
            files = glob.glob(self.config["media"]["path"])
            wakeup_song_path = random.choice(files)
            self.media_play_thread.song_path = wakeup_song_path

            event_logger.info("Set wakeup song to %s", wakeup_song_path)

        # Initialize the selected TTS engine with the generated content
        if self._tts_enabled():
            try:
                self.tts_client = self.get_tts_client()
                if self.tts_client is not None:
                    self.audio_segments = [
                        (section, self.tts_client.setup(text))
                        for section, text in contents
                    ]
            except Exception:
                event_logger.exception("TTS setup failed; alarm will use the beep")
                self.tts_client = None
                self.audio_segments = []

        if not self.audio_segments and (
            self._tts_enabled() or not self.config["media"]["enabled"]
        ):
            self.audio_segments = [("beep", self._load_beep_audio())]

        if self.audio_segments:
            self.audio = self.audio_segments[0][1]
            silence = pydub.AudioSegment.silent(duration=300)
            for _, audio in self.audio_segments[1:]:
                self.audio += silence + audio

    def play(self):
        """Play an alarm.
        
        If TTS is enabled, play the content of a pre-built alarm.
        Otherwise play a beeping sound effect. 
        """
        # Play wakeup song if enabled
        wakeup_song_enabled = self.config["media"]["enabled"]
        tts_enabled = self._tts_enabled()

        if wakeup_song_enabled:
            self.media_play_thread.start()
            self.media_play_thread.wait()
            self.media_play_thread.stop()

        if self._playback_cancelled.is_set():
            return

        if not self.audio_segments and not wakeup_song_enabled:
            self.audio_segments = [("beep", self._load_beep_audio())]

        for section, audio in self.audio_segments:
            if self._playback_cancelled.is_set():
                break
            try:
                self.audio_player.play(audio)
            except Exception:
                if self._playback_cancelled.is_set():
                    break
                event_logger.exception("Playback failed for %s; using the beep", section)
                if section != "beep":
                    try:
                        self.audio_player.play(self._load_beep_audio())
                    except Exception:
                        event_logger.exception("Beep playback failed")
                break

        # Reset audio for next alarm
        self.audio = None
        self.audio_segments = []

    def build_and_play(self):
        """Build and play an alarm.

        This is provided as a dedicated CLI interface for playing an alarm
        without GUI interaction.
        Since the alarm is built on the go there may be some delay on play.
        """
        self.build()
        self.play()

        # Play the radio stream if enabled
        if self.config["radio"]["enabled"]:
            self.play_radio()

    def stop(self):
        """Cancel alarm playback and stop the current audio segment."""
        self._playback_cancelled.set()
        self.audio_player.stop()
        self.media_play_thread.stop()

    def skip_current(self):
        """Stop the current song or audio segment and continue the alarm."""
        if self.media_play_thread.isRunning():
            self.media_play_thread.stop()
        else:
            self.audio_player.stop()

    def generate_greeting(self):
        """Generate a greeting using get_greeting.py handler.
        Return:
            the greeting as string.
        """
        greeter = get_greeting.Greeting(self.config)
        greeter.build()
        return greeter.get()

    def get_tts_client(self):
        """Create the TTS engine selected in the main configuration section.
        """
        section = self.config["main"].get("TTS")
        if not self._tts_enabled():
            event_logger.info("TTS is disabled or no TTS engine is selected")
            return None

        event_logger.info("Using TTS handler %s", section["handler"])
        class_ = get_handler("tts", section["handler"])
        return class_(auth=section.get("auth"), config=section)

    def _tts_enabled(self):
        section = self.config["main"].get("TTS")
        return bool(
            section
            and section.get("enabled", True)
            and section.get("handler")
        )

    def play_radio(self):
        """Open a stream to the default radio station using cvlc."""
        default_station = self.config["radio"]["default"]
        url = self.config["radio"]["urls"][default_station]

        args = self.config["radio"].get("args", "")
        cmd = f"/usr/bin/cvlc {url} {args}".split()
        # Run the command via Popen directly to open the stream as a child process without
        # waiting for it to finish.
        subprocess.Popen(cmd)

    @staticmethod
    def _load_beep_audio():
        path = str(utils.PATH_TO_RESOURCES / "Cool-alarm-tone-notification-sound.mp3")
        return pydub.AudioSegment.from_mp3(path)


class MediaPlayWorker(QThread):
    """Worker for playing a media file in a separate thread."""
    play_started_signal = pyqtSignal(str)
    play_finished_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.song_path = None
        self.process = None

    def run(self):
        """Start a vlc process and notify the GUI to display a window during the playback."""
        # Format a song name to display
        metadata = utils.get_mp3_metadata(self.song_path)
        song_name = (metadata["artist"] + " - " + metadata["title"]).lstrip("- ")

        process = subprocess.Popen(
            ["/usr/bin/cvlc", self.song_path, "vlc://quit"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.process = process
        self.play_started_signal.emit(song_name)
        try:
            process.wait()
        finally:
            if self.process is process:
                self.process = None
            self.play_finished_signal.emit(1)

    def stop(self):
        """Stop the wake-up track's VLC process."""
        event_logger.debug("Stopping media thread")
        process = self.process
        if process is None or process.poll() is not None:
            return

        try:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        except ProcessLookupError:
            return