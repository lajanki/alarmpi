#!/bin/bash


# Ensure backlight is turned on (Raspberry Pi)
if [[ -d "/sys/class/backlight/rpi_backlight" ]]; then
    echo 0 > /sys/class/backlight/rpi_backlight/bl_power
    echo 255 > /sys/class/backlight/rpi_backlight/brightness
fi

if [[ -d "/sys/class/backlight/10-0045" ]]; then
    echo 0 > /sys/class/backlight/10-0045/bl_power
    echo 255 > /sys/class/backlight/10-0045/brightness
fi

# Find the main alarmpi process and stop it if found
pid=$(pgrep -f "bin/alarmpi")

if [ -z "$pid" ]; then
    exit 0
fi

# Send a debug signal
kill -s USR1 $pid

# Stop any running alarms
pkill cvlc
pkill -f "play_alarm.py"
kill $pid 2>/dev/null