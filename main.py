#!/usr/bin/env python

# Entrypoint for the project, runs the clock GUI. The GUI can be used to
# schedule an alarm. To run the alarm directly, run alarm_builder.py.

import argparse
import logging
import logging.config
import sys

from PyQt5.QtWidgets import QApplication

from alarmpi.core import clock


logging.config.fileConfig("logging.conf")
event_logger = logging.getLogger("eventLogger")


def backlight_excepthook(type, value, tb):
    """Custom exception handler for uncaught exceptions.
    From the docs (https://docs.python.org/3/library/sys.html#sys.excepthook):
        When an exception is raised and uncaught, the interpreter calls sys.excepthook with three arguments,
        the exception class, exception instance, and a traceback object. In an interactive session this happens
        just before control is returned to the prompt; in a Python program this happens just before the program
        exits. The handling of such top-level exceptions can be customized by assigning another three-argument
        function to sys.excepthook.

    If the program crashes due to an unpredictable cause, such as network error on API call, while the screen is blank
    it is difficult to turn it back on again (usually this means SSH'ing in and running stop.sh).
    By overwriting the default handler we can take care of this automatically.

    Note that screen blanking is disabled when the host system is not a Raspberry Pi.
    https://stackoverflow.com/questions/20829300/is-there-a-way-to-have-a-python-program-run-an-action-when-its-about-to-crash
    """
    import traceback
    import subprocess
    tbtext = "".join(traceback.format_exception(type, value, tb))
    event_logger.critical(tbtext)
    subprocess.run("./stop.sh")


if __name__ == "__main__":
    sys.excepthook = backlight_excepthook

    parser = argparse.ArgumentParser(description="Run alarmpi GUI")
    parser.add_argument("config", metavar="config", nargs="?",
                        default="configs/default.yaml", help="Configuration file to use. Defaults to configs/default.yaml")
    parser.add_argument("--fullscreen", action="store_true",
                        help="fullscreen mode")
    parser.add_argument("--debug", action="store_true",
                        help="debug mode")
    args = parser.parse_args()

    if args.config == parser.get_default("config"):
        event_logger.info("No config specified, defaulting to %s", args.config)

    kwargs = vars(args)
    config = kwargs.pop("config")

    app = QApplication(sys.argv)
    with open("style.qss") as f:
        app.setStyleSheet(f.read())

    if args.debug:
        # Add visible border around elements
        app.setStyleSheet( app.styleSheet() + "AlarmWindow QLabel, QLCDNumber {border: 1px solid red;}")

        event_logger.info("Setting event_logger level to DEBUG")
        event_logger.setLevel(logging.DEBUG)
        for handler in event_logger.handlers:
            handler.setLevel(logging.DEBUG)

    ex = clock.Clock(config, **kwargs)
    ex.setup()
    res = app.exec_()

    sys.exit(res)
