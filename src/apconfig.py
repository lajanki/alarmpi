# Wrapper class for reading alarm configuration file.

import glob
import logging
import os
from datetime import datetime

import yaml
from src import rpi_utils


logger = logging.getLogger("eventLogger")


class AlarmConfig:
    """Parses the configuration file to a readable object."""

    def __init__(self, config_file):
        """Setup and validate a configuration object from file.
        params
            config_file (str): path to a configuration file to use.
        """
        self.config_file = config_file
        with open(self.config_file) as f:
            self.config = yaml.safe_load(f)

        try:
            self.validate()
        except AssertionError as e:
            msg = "Couldn't validate configuration file {}.\nError received was: {}.\
            \nSee configs/default.yaml for reference.\
            ".format(self.config_file, e)
            raise RuntimeError(msg) from e
        except KeyError as e:
            msg = "Couldn't validate configuration file {}.\nMissing key detected: {}.\
            \nSee configs/default.yaml for reference.\
            ".format(self.config_file, e)
            raise RuntimeError(msg) from e

        # Check for write access to Raspberry Pi system backlight brightness files
        self.rpi_brightness_write_access = all(
            [
                os.access(p, os.W_OK)
                for p in [rpi_utils.BRIGHTNESS_FILE, rpi_utils.POWER_FILE]
            ]
        )

    def __getitem__(self, item):
        # Make the object subscriptable for convenience
        return self.config[item]

    def __setitem__(self, item, value):
        self.config[item] = value

    def validate(self):
        """Validate configuration file: checks that
        * content and TTS sections have 'handler' key
        * at most 1 TTS engine is enabled
        * low_brightness value is valid
        * default radio station is valid
        * nighttime values are in HH:MM
        * alarm_time is in HH:MM
        """

        for item in self["content"]:
            assert "handler" in self["content"][item], (
                "Missing handler from content" + item
            )

        for item in self["TTS"]:
            assert "handler" in self["TTS"][item], "Missing handler from TTS" + item

        n_tts_enabled = len(
            [
                self["TTS"][item]["enabled"]
                for item in self["TTS"]
                if self["TTS"][item]["enabled"]
            ]
        )
        assert n_tts_enabled <= 1, "Multiple TTS enabled engines not allowed"

        brightness = self["main"]["low_brightness"]
        assert (
            9 <= brightness <= 255
        ), "Invalid configuration: Brightness should be between 9 and 255"

        default = self["radio"]["default"]
        assert default in self["radio"]["urls"], (
            "No stream url for defult radio station" + default
        )

        try:
            datetime.strptime(self["main"]["nighttime"]["start"], "%H:%M")
            datetime.strptime(self["main"]["nighttime"]["end"], "%H:%M")
        except ValueError as e:
            raise AssertionError("Invalid time value for nighttime: " + e.args[0])

        try:
            datetime.strptime(self["main"]["alarm_time"], "%H:%M")
        except ValueError as e:
            logger.warning("alarm_time %s is not valid, Defaulting to 07:00", self["main"]["alarm_time"])
            self["main"]["alarm_time"] = "07:00"

        if self["media"]["enabled"]:
            assert glob.glob(self["media"]["path"]), "Path to wakeup song is not valid"

        return True

    def get_enabled_sections(self, type):
        """Return names of sections sections whose 'type' is section_type (either 'content' or 'tts')."""
        return {k: v for k, v in self[type].items() if self[type][k].get("enabled")}

    def _get_debug_option(self, option):
        """Get a key from the debug section. The debug section is not defined in the config,
        but set during config creation in clock.py. Therefore this section may not exist at runtime.
        """
        return self.config.get("debug", {}).get(option)