# Send a debug signal to the alarmpi process
kill -s USR1 $(pgrep -f "bin/alarmpi")