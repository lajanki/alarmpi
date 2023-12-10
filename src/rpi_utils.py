# Collectin of Raspberry Pi related helper functions for interacting with screen
# brightness.

import logging
import os
from functools import wraps


logger = logging.getLogger("eventLogger")


HIGH_BRIGHTNESS = 255
BRIGHTNESS_FILE = "/sys/class/backlight/10-0045/brightness"
POWER_FILE = "/sys/class/backlight/10-0045/bl_power"

# Older backlight control files for pre-Debian Bullseye based Raspberry OS release
if not os.path.exists(BRIGHTNESS_FILE):
    BRIGHTNESS_FILE = "/sys/class/backlight/rpi_backlight/brightness"
    POWER_FILE = "/sys/class/backlight/rpi_backlight/bl_power"


IS_RASPBERRY_PI = False
try:
    with open("/sys/firmware/devicetree/base/model") as f:
        if "raspberry pi" in f.read().lower():
            IS_RASPBERRY_PI = True
except Exception:
    pass


def require_rpi(func):
    """Wrapper for skipping function calls if not running on a Raspberry Pi."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if IS_RASPBERRY_PI:
            func(*args, **kwargs)
        else:
            logger.warning(
                "Not running on a Raspberry Pi, ignoring utility function %s",
                func.__name__
            )
    return wrapper

@require_rpi
def set_display_backlight_brightness(brightness):
    """Write a new brightness value to file."""
    with open(BRIGHTNESS_FILE, "w") as f:
        f.write(str(brightness))

def toggle_display_backlight_brightness(low_brightness=12):
    """Reads current brightness value and toggles it between
    low and max values depending on current value.
    """
    old = _get_current_display_backlight_brightness()

    # set to furthest away from current brightness
    if abs(old-low_brightness) < abs(old-HIGH_BRIGHTNESS):
        new = HIGH_BRIGHTNESS
    else:
        new = low_brightness

    set_display_backlight_brightness(new)

@require_rpi
def toggle_screen_state(state="on"):
    """Toggle screen state between on / off."""
    value = 1
    if state == "on":
        value = 0

    with open(POWER_FILE, "w") as f:
        f.write(str(value))

@require_rpi
def get_and_set_screen_state(new_state):
    """Read the current screen power state and set it to new_state. Returns the
    previous value (on/off).
    """
    with open(POWER_FILE, "r+") as f:
        previous_value = f.read().strip()

        f.seek(0)
        value = 1
        if new_state == "on":
            value = 0
        f.write(str(value))

    if previous_value == 0:
        return "on"
    return "off"

@require_rpi
def _get_current_display_backlight_brightness():
    """Return the current backlight brightness value."""
    with open(BRIGHTNESS_FILE, "r") as f:
        try:
            value = int(f.read().strip())
        # default to max value if unable to read the file
        except ValueError:
            value = HIGH_BRIGHTNESS

    return value
