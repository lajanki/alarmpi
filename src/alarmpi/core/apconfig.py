# Wrapper class for reading alarm configuration file.

import glob
import logging
import os
from datetime import datetime

import yaml
from alarmpi.handlers import is_registered_handler
from alarmpi.utils import rpi_utils
from alarmpi.core.GUIWidgets import Status


logger = logging.getLogger("eventLogger")


class ConfigValidationError(ValueError):
    """The configuration file is missing a key or contains an invalid value."""


def _require(condition, message):
    # Explicit raise: unlike assert, it survives python -O.
    if not condition:
        raise ConfigValidationError(message)

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
        except ConfigValidationError as e:
            raise ConfigValidationError(self._describe(e)) from None
        except KeyError as e:
            raise ConfigValidationError(self._describe(f"missing key {e}")) from None

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

    def _describe(self, problem):
        return (
            f"Invalid configuration file {self.config_file}: {problem}. "
            "See configs/default.yaml for reference."
        )

    def validate(self):
        """Validate configuration file: checks that
            * content sections are registered handlers or define text
            * main.TTS.engine, if set, is a registered TTS engine
            * low_brightness value is within range
            * default radio station url is known
            * nighttime values are in HH:MM
            * alarm_time is in HH:MM, if set
            * media path pattern is not empty
        """

        for item in self["content"]:
            section = self["content"][item]
            has_text = "text" in section
            has_handler = is_registered_handler("content", item.lower())

            _require(
                has_handler != has_text,
                f"Content {item} must be a registered handler section or define text",
            )
            if has_text:
                _require(
                    isinstance(section["text"], str),
                    f"Content text must be a string: {item}",
                )

        tts_config = self["main"].get("TTS")
        if tts_config is not None:
            _require(isinstance(tts_config, dict), "main.TTS must be a mapping or null")
            tts_engine = tts_config.get("engine")
            _require(
                tts_engine is None
                or (isinstance(tts_engine, str) and is_registered_handler("tts", tts_engine)),
                f"Unknown TTS engine {tts_engine}",
            )

        # If GCP TTS is selected, check if ADC credentials are available.
        if tts_config and tts_config.get("enabled", True) and tts_config.get("engine") == "gcp":
            import google.auth
            try:
                google.auth.default()
            except Exception as e:
                raise ConfigValidationError(
                    f"GCP TTS enabled but unable to load credentials ({e}). "
                    "Is GOOGLE_APPLICATION_CREDENTIALS set?"
                ) from e

        brightness = self["main"]["low_brightness"]
        _require(9 <= brightness <= 255, "Brightness should be between 9 and 255")

        startup_volume = self["alsa"].get("startup_volume")
        _require(
            startup_volume is None or (
                isinstance(startup_volume, int)
                and not isinstance(startup_volume, bool)
                and 0 <= startup_volume <= 100
            ),
            "startup_volume must be between 0 and 100",
        )

        default = self["radio"]["default"]
        _require(
            default in self["radio"]["urls"],
            f"No stream url for default radio station: {default}",
        )

        try:
            datetime.strptime(self["main"]["nighttime"]["start"], "%H:%M")
            datetime.strptime(self["main"]["nighttime"]["end"], "%H:%M")
        except ValueError as e:
            raise ConfigValidationError("Invalid time value for nighttime: " + e.args[0]) from e

        alarm_time = self["main"].get("alarm_time")
        if alarm_time:
            try:
                datetime.strptime(alarm_time, "%H:%M")
            except ValueError as e:
                logger.warning("alarm_time %s is not valid. Alarm not active.", alarm_time)
                self.config["main"]["alarm_time"] = Status.EMPTY.value

        # Media path should contain at least 1 file.
        # Content of the file is *not* validated, vlc will silently ignore unsupported files.
        if self["media"]["enabled"]:
            _require(glob.glob(self["media"]["path"]), "Path to wakeup song is not valid")

        return True

    def get_enabled_sections(self, type):
        """Return names of sections sections whose 'type' is section_type (either 'content' or 'tts')."""
        return {k: v for k, v in self[type].items() if self[type][k].get("enabled")}

    def _get_debug_option(self, option):
        """Get a key from the debug section. The debug section is not defined in the config,
        but set during config creation in clock.py. Therefore this section may not exist at runtime.
        """
        return self.config.get("debug", {}).get(option)
