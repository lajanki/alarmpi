import glob
import logging
import os
import random
import subprocess

import pydub
import pydub.playback
from PyQt5.QtCore import QThread, pyqtSignal

from alarmpi.utils import utils
from alarmpi.handlers import get_handler, get_greeting


event_logger = logging.getLogger("eventLogger")


class AlarmBuilder:

    def __init__(self, config):
        self.media_play_thread = MediaPlayWorker()
        self.config = config
        self.audio = None

    def build(self):
        """Build an alarm.

        Loop through the configuration file for enabled content sections
        and generate matching content.
        """
        self.audio = None
        self.tts_client = None

        # Initialize content with greeting
        contents = []
        contents.append(self.generate_greeting())

        # For each content section get the handler module and create the approriate
        # content parser
        content_sections = self.config.get_enabled_sections("content")
        for section in content_sections:
            section_data = content_sections[section]
            if "text" in section_data:
                contents.append(section_data["text"])
                continue

            class_ = get_handler("content", section_data["handler"])
            parser = class_(section_data)

            # build content
            parser.build()
            contents.append(parser.get())

        for section in contents:
            print(section)

        if self.config["media"]["enabled"]:
            files = glob.glob(self.config["media"]["path"])
            wakeup_song_path = random.choice(files)
            self.media_play_thread.song_path = wakeup_song_path

            event_logger.info("Set wakeup song to %s", wakeup_song_path)

        # Initialize the selected TTS engine with the generated content
        if self.config["main"].get("TTS"):
            try:
                self.tts_client = self.get_tts_client()
                if self.tts_client is not None:
                    content_text = "\n".join(contents)
                    self.audio = self.tts_client.setup(content_text)
            except Exception:
                event_logger.exception("TTS setup failed; alarm will use the beep")
                self.tts_client = None

    def play(self):
        """Play an alarm.
        
        If TTS is enabled, play the content of a pre-built alarm.
        Otherwise play a beeping sound effect. 
        """
        # Play wakeup song if enabled
        wakeup_song_enabled = self.config["media"]["enabled"]
        tts_enabled = bool(self.config["main"].get("TTS"))

        # Default to a beepig alarm if nether TTS or wakeup song is enabled
        if not any([tts_enabled, wakeup_song_enabled]):
            AlarmBuilder.play_beep()
            return

        if wakeup_song_enabled: 
            self.media_play_thread.start()
            self.media_play_thread.wait()
            self.media_play_thread.stop()

        if tts_enabled and self.audio is not None and self.tts_client is not None:
            try:
                self.tts_client.play(self.audio)
            except Exception:
                event_logger.exception("TTS playback failed; using the beep")
                AlarmBuilder.play_beep()
        elif tts_enabled:
            event_logger.warning("No TTS audio available; using the beep")
            AlarmBuilder.play_beep()

        # Reset audio for next alarm
        self.audio = None

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
        """Stop currently playing TTS audio, if a client has been initialized."""
        tts_client = getattr(self, "tts_client", None)
        if tts_client is not None:
            tts_client.stop()

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
        if not section:
            event_logger.info("No TTS engine selected")
            return None

        event_logger.info("Using TTS handler %s", section["handler"])
        class_ = get_handler("tts", section["handler"])
        return class_(auth=section.get("auth"), config=section)

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
    def play_beep():
        """Play a beeping sound effect."""
        path = str(utils.PATH_TO_RESOURCES / "Cool-alarm-tone-notification-sound.mp3")
        beep = pydub.AudioSegment.from_mp3(path)
        pydub.playback.play(beep)

        return path


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

        self.play_started_signal.emit(song_name)
        self.process = subprocess.run(["/usr/bin/cvlc", self.song_path, "vlc://quit"])

    def stop(self):
        """Terminate the thread."""
        event_logger.debug("Stopping media thread")
        self.play_finished_signal.emit(1)
        # The vlc process needs to be explicitely terminated
        try:
            subprocess.run(["killall", "-9", "vlc"], stderr=subprocess.DEVNULL)
            self.process.terminate()

        except AttributeError:
            return