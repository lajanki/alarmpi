import json
import os.path
import re
import subprocess
from datetime import datetime, date, timedelta

from mutagen.id3 import ID3, ID3NoHeaderError
from PyQt5.QtGui import QPixmap

BASE = os.path.join(os.path.dirname(__file__), "..")


class DateTimeEncoder(json.JSONEncoder):
    """Custom json encoder handling datetime objects."""
    def default(self, z):
        if isinstance(z, datetime):
            return (str(z))
        return super().default(z)


def time_str_to_dt(s):
    """Convert a time string in HH:MM format to a datetime object.
    By default the date is set to current date.
    Args:
        s (str): time string in %H:%M format
        use_next_available_date (boolean): sets the date to tomorrow if the time
            has already passed for the current date. 
    """
    today = date.today()
    dummy_dt = datetime.strptime(s, "%H:%M")
    dt = dummy_dt.replace(year=today.year, month=today.month, day=today.day)
    return dt

def get_volume(card):
    """Get current audio volume level from amixer as integer from 0 to 100.
    Args:
        card (int): the sound card to read, see aplay -l for list of
        cards available.
    """
    res = subprocess.run("amixer -c {} sget PCM".format(card).split(), capture_output=True)

    # Response contains volume level as percentage, parse the digits
    s = re.search("\[(\d*)%\]", res.stdout.decode("utf8"))
    return int(s.group(1))

def set_volume(card, level):
    """Set audio volume.
    Args:
        card (int): same as get_volume
        level (int): volume level as percentage, 0 - 100
    """
    subprocess.run("amixer --quiet -c {} sset PCM {}%".format(card, level).split())

def get_volume_icon(mode):
    """Determine icon set to use as volume level. If Adwaita Ubuntu theme exists use its icons.
    Otherwise use custom icons.
    Args:
        mode (str): volume level: muted/low/medium/high
    Return:
        QPixmap object matching the mode
    """

    SYSTEM_THEME_BASE = "/usr/share/icons/Adwaita/32x32/status/"
    if os.path.isfile(os.path.join(SYSTEM_THEME_BASE, "audio-volume-high-symbolic.symbolic.png")):
        img_map = {
            "muted": os.path.join(SYSTEM_THEME_BASE, "audio-volume-muted-symbolic.symbolic.png"),
            "low": os.path.join(SYSTEM_THEME_BASE, "audio-volume-low-symbolic.symbolic.png"),
            "medium": os.path.join(SYSTEM_THEME_BASE, "audio-volume-medium-symbolic.symbolic.png"),
            "high": os.path.join(SYSTEM_THEME_BASE, "audio-volume-high-symbolic.symbolic.png")
        }
        return QPixmap(img_map[mode])

    else:
        original = QPixmap(os.path.join(BASE, "resources", "icons", "volume_640.png"))
        Y = 70
        HEIGHT = 212

        img_map = {
            "muted": original.copy(0, Y, 172, HEIGHT),
            "low": original.copy(165, Y, 198, HEIGHT),
            "medium": original.copy(165, Y, 198, HEIGHT), # same as low
            "high": original.copy(375, Y, 258, HEIGHT)
        }

        return img_map[mode].scaledToHeight(32)

def get_mp3_metadata(file):
    """Read ID3 tag of an mp3 file.
    Args:
        file (str): path to audio file
    Return:
        A dictionary containing artist and title. Default to 
        filename if ID3 tags cannot be read.
    """
    try:
        audio = ID3(file)
        metadata = {
            "artist": audio["TPE2"].text[0],
            "title": audio["TIT2"].text[0]
        }
    except ID3NoHeaderError as e:
        metadata = {
            "artist": "",
            "title": os.path.basename(file)
        } 
    return metadata
