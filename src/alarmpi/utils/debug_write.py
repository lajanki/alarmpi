from datetime import datetime
import json
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication



event_logger = logging.getLogger("eventLogger")


class DateTimeEncoder(json.JSONEncoder):
    """Custom json encoder handling datetime objects."""

    def default(self, z):
        if isinstance(z, datetime):
            return str(z)
        return super().default(z)


def signal_handler(config, sig=None, frame=None):
    """Dump current program state to file."""
    OUTPUT_FILE = "debug_info.txt"
    app = QApplication.instance()

    with open(OUTPUT_FILE, "w") as f:
        f.write(f"Config snapshot from: {datetime.now().isoformat()}\n")
        
        # Highlight config file name
        f.write("\n=== Config File Name ===\n")
        f.write(f"config file: {config.config_file}\n")
        
        # Highlight config file content
        f.write("\n=== Config File Content ===\n")
        json.dump(config.config, f, indent=4, cls=DateTimeEncoder)
        
        # Highlight window states
        f.write("\n=== Window States ===\n")
        f.write(
            "\n{:<20} {:<10} {:<15} {:<15} {:<10}".format(
                "window", "isVisible", "isFullScreen", "isActiveWindow", "isEnabled"
            )
        )
        for window in app.topLevelWidgets():
            f.write(
                "\n{:<20} {:<10} {:<15} {:<15} {:<10}".format(
                    window.__class__.__name__,
                    window.isVisible(),
                    window.isFullScreen(),
                    window.isActiveWindow(),
                    window.isEnabled(),
                )
            )

    event_logger.info("Debug status written to %s", OUTPUT_FILE)
