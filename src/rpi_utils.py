# Collectin of Raspberry Pi related helper functions for interacting with screen
# brightness.

import tempfile
import logging
import inspect
import os


logger = logging.getLogger("eventLogger")


HIGH_BRIGHTNESS = 255
BRIGHTNESS_FILE = "/sys/class/backlight/10-0045/brightness"
POWER_FILE = "/sys/class/backlight/10-0045/bl_power"

# Older backlight control files for pre Debian Bullseye based Raspberry OS release
if not os.path.exists(BRIGHTNESS_FILE):
    BRIGHTNESS_FILE = "/sys/class/backlight/rpi_backlight/brightness"
    POWER_FILE = "/sys/class/backlight/rpi_backlight/bl_power"


def set_display_backlight_brightness(brightness):
    """Write a new brightness value to file."""
    with _get_config_file_or_tempfile(BRIGHTNESS_FILE, "w") as f:
        f.write(str(brightness))

def toggle_display_backlight_brightness(low_brightness=12):
    """Reads Raspberry pi touch display's current brightness values from system
    file and toggles it between low and max (255) values depending on the
    current value.
    """
    old = _get_current_display_backlight_brightness()

    # set to furthest away from current brightness
    if abs(old-low_brightness) < abs(old-HIGH_BRIGHTNESS):
        new = HIGH_BRIGHTNESS
    else:
        new = low_brightness

    set_display_backlight_brightness(new)

def toggle_screen_state(state="on"):
    """Toggle screen state between on / off."""
    value = 1
    if state == "on":
        value = 0

    with _get_config_file_or_tempfile(POWER_FILE, "w") as f:
        f.write(str(value))

def get_and_set_screen_state(new_state):
    """Read the current screen power state and set it to new_state. Returns the
    previous value ('on'/'off').
    """
    with _get_config_file_or_tempfile(POWER_FILE, "r+") as f:
        previous_value = f.read().strip()

        f.seek(0)
        value = 1
        if new_state == "on":
            value = 0
        f.write(str(value))

    if previous_value == 0:
        return "on"
    return "off"

def _get_current_display_backlight_brightness():
    """Return the current backlight brightness value."""
    with _get_config_file_or_tempfile(BRIGHTNESS_FILE, "r") as f:
        try:
            value = int(f.read().strip())
        except ValueError:
            value = HIGH_BRIGHTNESS  # default to max value if unable to read the file (ie. is a dummy tempfile)

    return value

def _get_config_file_or_tempfile(file_path, mode="r"):
    """Return a file object matching a file path. Returns either a
    file object pointing to an existing file or a TemporaryFile if the file
    does not exist.
    """
    try:
        return open(file_path, mode=mode)
    except FileNotFoundError:
        stack_value = inspect.stack()[1]
        function = stack_value.function
        argvalues = inspect.getargvalues(stack_value.frame)

        logger.warning(
            "Using tempfile instead of non-existing file %s when calling %s with arguments: %s",
            file_path,
            function,
            inspect.formatargvalues(*argvalues)
        )
        return tempfile.TemporaryFile(mode=mode)
    except PermissionError as e:
        logging.warning("Couldn't open file %s, using tempfile instead. Original error was\n%s", file_path, str(e))
        return tempfile.TemporaryFile(mode=mode)
