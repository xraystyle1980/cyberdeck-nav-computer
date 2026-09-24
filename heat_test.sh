#!/bin/sh
# Load all CPU cores to heat the Pi, printing temperature and fan speed.
# Usage: ./heat_test.sh [seconds]   (default 180; Ctrl+C stops early)

DURATION=${1:-180}
FAN=$(ls /sys/class/hwmon/hwmon*/fan1_input 2>/dev/null | head -1)

PIDS=""
for i in $(seq "$(nproc)"); do yes >/dev/null 2>&1 & PIDS="$PIDS $!"; done
trap 'kill $PIDS 2>/dev/null; echo "load stopped"; trap - EXIT; exit' INT TERM EXIT

echo "loading $(nproc) cores for ${DURATION}s"
end=$(( $(date +%s) + DURATION ))
while [ "$(date +%s)" -lt "$end" ]; do
    t=$(cat /sys/class/thermal/thermal_zone0/temp)
    printf '%4ss  %d.%d °C  fan %s RPM\n' "$(( DURATION - end + $(date +%s) ))" \
        $((t / 1000)) $((t % 1000 / 100)) "$(cat "$FAN" 2>/dev/null || echo ?)"
    sleep 5
done
