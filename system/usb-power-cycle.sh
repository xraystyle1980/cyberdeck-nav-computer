#!/bin/sh
# Cut and restore power on every USB port so the Corne keyboard restarts
# with Linux ready to talk to it. Pi 5 port power is ganged, so all four
# root hubs must go off together. The HDMI screen is USB-powered too, so
# wait for it to reconnect before the desktop starts.

for h in 1 2 3 4; do /usr/sbin/uhubctl -l $h -a off >/dev/null; done
sleep 3
for h in 1 2 3 4; do /usr/sbin/uhubctl -l $h -a on >/dev/null; done

for i in $(seq 1 30); do
    if grep -qx connected /sys/class/drm/card*-HDMI-A-1/status 2>/dev/null; then
        echo "USB power cycled; screen connected after $((i / 2))s"
        sleep 1  # let the screen finish reporting its modes
        exit 0
    fi
    sleep 0.5
done
echo "USB power cycled; screen not detected after 15s, continuing anyway"
