# Creates a demo alarm with greeting, weather and news and stores as an mp3 file.

import argparse
from alarmpi.core import alarm_builder, apconfig


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a demo alarm as mp3 file.")
    parser.add_argument("config", metavar="config", nargs="?",
                        default="configs/default.yaml", help="Configuration file to use.")
    args = parser.parse_args()

    config = apconfig.AlarmConfig(args.config)
    builder = alarm_builder.AlarmBuilder(config)

    builder.build()
    builder.audio.export("demo.mp3", format="mp3")
