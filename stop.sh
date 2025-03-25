#!/bin/bash

# Get the process ID of the running alarmpi process
pid=$(pgrep -f "bin/alarmpi")

# Send a debug signal
kill -s USR1 $pid


# stop any running alarms
pkill cvlc
pkill -f "play_alarm.py"
kill $pid

# Ensure backlight is turned on (only on Raspberry Pi)
if [[ -d "/sys/class/backlight/rpi_backlight" ]]; then
    echo 0 > /sys/class/backlight/rpi_backlight/bl_power
    echo 255 > /sys/class/backlight/rpi_backlight/brightness
fi

if [[ -d "/sys/class/backlight/10-0045" ]]; then
    echo 0 > /sys/class/backlight/10-0045/bl_power
    echo 255 > /sys/class/backlight/10-0045/brightness
fi