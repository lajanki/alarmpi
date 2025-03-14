import glob
import importlib
import inspect
import logging
import os
import random
import requests.exceptions
import subprocess

import pydub
import pydub.playback
from PyQt5.QtCore import QThread, pyqtSignal

from alarmpi.utils import utils
from alarmpi.handlers import get_festival_tts, get_greeting


event_logger = logging.getLogger("eventLogger")


class AlarmBuilder:

    def __init__(self, config):
        self.media_play_thread = MediaPlayWorker()
        self.config = config
        self.audio = None

    def build(self):
        """Loop through the configuration file for enabled content sections
        and generate content.
        """
        # Initialize content with greeting
        contents = []
        contents.append(self.generate_greeting())

        # For each content section get the handler module and create the approriate
        # content parser
        content_sections = self.config.get_enabled_sections("content")
        for section in content_sections:
            class_ = self.get_content_parser_class(content_sections[section])
            parser = class_(content_sections[section])

            # build content
            parser.build()
            contents.append(parser.get())

        # Add ending phrase from the config file
        contents.append(self.config["main"].get("end", ""))

        for section in contents:
            print(section)

        if self.config["media"]["enabled"]:
            files = glob.glob(self.config["media"]["path"])
            wakeup_song_path = random.choice(files)
            self.media_play_thread.song_path = wakeup_song_path

            event_logger.info("Set wakeup song to %s", wakeup_song_path)

        # Initialize TTS client with the generated content
        if self.config["main"]["TTS"]:
            self.tts_client = self.get_tts_client()
            content_text = "\n".join(contents)
            self.audio = self.tts_client.setup(content_text)

    def play(self):
        """Play an alarm. Either play a pre-built alarm via the configured TTS client
        or play a beeping sound effect.
        """
        # Play wakeup song if enabled
        wakeup_song_enabled = self.config["media"]["enabled"]
        tts_enabled = self.config["main"]["TTS"]

        # Default to a beepig alarm if nether TTS or wakeup song is enabled
        if not any([tts_enabled, wakeup_song_enabled]):
            AlarmBuilder.play_beep()
            return

        if wakeup_song_enabled: 
            self.media_play_thread.start()
            self.media_play_thread.wait()
            self.media_play_thread.stop()

        if self.audio:
            try:
                self.tts_client.play(self.audio)
            except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
                event_logger.error(str(e))
                event_logger.info("Defaulting to alarm sound effect")
                AlarmBuilder.play_beep()

        # Reset audio for next alarm
        self.audio = None

    def build_and_play(self):
        """Build and play an alarm.
        This is provided as a CLI interface for playing the alarm.
        Since the alarm is built on the go, there may be a few seconds delay on play.
        """
        self.play()

        # Play the radio stream if enabled
        if self.config["radio"]["enabled"]:
            self.play_radio()

    def generate_greeting(self):
        """Generate a greeting using get_greeting.py handler.
        Return:
            the greeting as string.
        """
        greeter = get_greeting.Greeting(self.config)
        greeter.build()
        return greeter.get()

    def get_tts_client(self):
        """Determine which TTS engine to use based on the enabled tts sections
        in the config file. First enabled section is used.
        """
        # Search for the first enabled TTS engine and instantiate a corresponding class
        section_wrapper = self.config.get_enabled_sections("TTS")

        if section_wrapper:
            section = list(section_wrapper.values())[0]
            event_logger.info("Using TTS handler %s", section["handler"])

            class_ = self.get_content_parser_class(section)
            # read the path to the keyfile if provided/applicable
            auth = section.get("auth")
            client = class_(auth=auth)

        # Default to Festival TTS
        else:
            event_logger.info("No TTS engine specified in config, using Festival")
            client = get_festival_tts.FestivalTTSManager()

        return client

    def get_content_parser_class(self, section):
        """Given config file section name, return the class matching the handler."""
        # use importlib to dynamically import the correct module within
        # the 'handlers' package.
        path_to_module = f"alarmpi.handlers.{section['handler'][:-3]}"
        handler_module = importlib.import_module(path_to_module)

        # Inspect the handler module for classes and return the first class.
        class_ = inspect.getmembers(handler_module, inspect.isclass)[0][1]

        return class_

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
        path = os.path.join(utils.BASE, "resources", "Cool-alarm-tone-notification-sound.mp3")
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