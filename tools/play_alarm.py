#!/usr/bin/env python

# Generates an alarm based on a configuration file and plays it. This module acts as
# the entry point to the actual alarm, and will be scheduled via cron.
# This module does not depend on the GUI and can therefore be scheduled manually
# to play an alarm.


import argparse

from alarmpi.core import alarm_builder
from alarmpi.core import apconfig


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Play an alarm using a specified configuration file")
    parser.add_argument("config", metavar="config", nargs="?",
                        default="configs/default.yaml", help="Configuration file to use. Defaults to configs/default.yaml")
    args = parser.parse_args()

    config = apconfig.AlarmConfig(args.config)

    alarm = alarm_builder.AlarmBuilder(config)
    alarm.build_and_play()
