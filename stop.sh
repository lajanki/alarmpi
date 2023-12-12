#!/bin/bash

# Send a debug signal to the main script
kill -s USR1 $(pgrep -f "python .*(alarmpi/)?main.py")


# kill any running alarms
pkill cvlc
pkill -f "play_alarm.py"
pkill -f "python .*(alarmpi/)?main.py"

# Ensure backlight is turned on (only on Raspberry Pi)
if [[ -d "/sys/class/backlight/rpi_backlight" ]]; then
    echo "exists"
    echo 0 > /sys/class/backlight/rpi_backlight/bl_power
    echo 255 > /sys/class/backlight/rpi_backlight/brightness
fi

if [[ -d "/sys/class/backlight/10-0045" ]]; then
    echo "exists"
    echo 0 > /sys/class/backlight/10-0045/bl_power
    echo 255 > /sys/class/backlight/10-0045/brightness
fi