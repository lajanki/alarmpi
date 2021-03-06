# Collectin of Raspberry Pi related helper functions for interacting with screen
# brightness.

import os
import subprocess
import tempfile
import logging
import inspect


HIGH_BRIGHTNESS = 255
BRIGHTNESS_FILE = "/sys/class/backlight/rpi_backlight/brightness"
POWER_FILE = "/sys/class/backlight/rpi_backlight/bl_power"

logger = logging.getLogger("eventLogger")


def _open_config_file_or_tempfile(file_path, mode="r"):
    """Returns a file object matching a file path. Returns either a
    file object pointing to an existing file or a tempfile if the file
    does not exist.
    """
    try:
        return open(file_path, mode=mode)
    except FileNotFoundError:
        logger.warning("Using tempfile instead of non-existing file %s when calling %s", file_path, inspect.stack()[1].function)
        return tempfile.TemporaryFile(mode=mode)
    except PermissionError as e:
        logging.warning("Couldn't open file %s, using tempfile. Original error was\n%s", file_path, str(e))
        return tempfile.TemporaryFile(mode=mode)

def set_display_backlight_brightness(brightness):
    """Write a new brightness value to file."""
    with _open_config_file_or_tempfile(BRIGHTNESS_FILE, "w") as f:
        f.write(str(brightness))

def get_current_display_backlight_brightness():
    """Return the current backlight brightness value."""
    with _open_config_file_or_tempfile(BRIGHTNESS_FILE, "r") as f:
        try:
            value = int(f.read().strip())
        except ValueError:
            value = HIGH_BRIGHTNESS # default to max value if unable to read the file (ie. is a dummy tempfile)

    return value

def toggle_display_backlight_brightness(low_brightness=12):
    """Reads Raspberry pi touch display's current brightness values from system
    file and toggles it between low and max (255) values depending on the
    current value.
    """
    old = get_current_display_backlight_brightness()

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

    with _open_config_file_or_tempfile(POWER_FILE, "w") as f:
        f.write(str(value))

def screen_is_powered():
    """Determine whether the screen backlight is currently on."""
    with _open_config_file_or_tempfile(POWER_FILE) as f:
        value = f.read().strip()

    return value == "0"

def get_and_set_screen_state(new_state):
    """Read the current screen power state and set it to new_state. Returns the
    previous value ('on'/'off').
    """
    with _open_config_file_or_tempfile(POWER_FILE, "r+") as f:
        previous_value = f.read().strip()

        f.seek(0)
        value = 1
        if new_state == "on":
            value = 0
        f.write(str(value))

    if previous_value == 0:
        return "on"
    return "off"


### Old xset based screens state functions
def toggle_screen_state_xset(state="on"):
    """Use xset utility to turn the screen on (the default)/off.
    Touching the screen will also activate the screen.
    """
    cmd = "xset dpms force on".split()
    if state == "off":
        cmd = "xset dpms force off".split()

    home = os.path.expanduser("~")
    xauthority = os.path.join(home, ".Xauthority")
    env = {"XAUTHORITY": xauthority, "DISPLAY": ":0"}
    subprocess.run(cmd, env=env)

def screen_is_powered_xset():
    """Use xset to get the current screen state: is it currently blank?
    returns True if screen is active
    """
    cmd = "xset q".split()
    res = subprocess.check_output(cmd)
    return "Monitor is On" in str(res)
