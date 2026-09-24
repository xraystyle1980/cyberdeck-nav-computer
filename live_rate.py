import signal
import sys
import tm1637
from time import monotonic, sleep

# Live download rate on the TM1637 display.
#   0-9999      -> KB/s
#   colon lit   -> MB/s (used once the rate passes 9999 KB/s)

CLK, DIO = 17, 27
INTERVAL = 1.0  # seconds between readings


def rx_bytes():
    """Total bytes received across all interfaces except loopback."""
    total = 0
    with open("/proc/net/dev") as f:
        for row in f.readlines()[2:]:
            iface, data = row.split(":", 1)
            if iface.strip() != "lo":
                total += int(data.split()[0])
    return total


def show_rate(tm, bytes_per_sec):
    kb = bytes_per_sec / 1024
    if kb <= 9999:
        tm.show(f"{round(kb):04d}")
    else:
        tm.show(f"{min(round(kb / 1024), 9999):04d}", colon=True)


def stop(tm):
    tm.show("    ")
    print("\nStopped — display cleared.")
    sys.exit(0)


tm = tm1637.TM1637(clk=CLK, dio=DIO)
tm.brightness(7)
signal.signal(signal.SIGTERM, lambda *_: stop(tm))

last_bytes, last_time = rx_bytes(), monotonic()
try:
    while True:
        sleep(INTERVAL)
        now_bytes, now_time = rx_bytes(), monotonic()
        # Counters reset if an interface goes down and back up
        delta = max(now_bytes - last_bytes, 0)
        rate = delta / (now_time - last_time)
        show_rate(tm, rate)
        if sys.stdout.isatty():  # stay quiet in the systemd journal
            print(f"\r{rate / 1024:10.1f} KB/s", end="", flush=True)
        last_bytes, last_time = now_bytes, now_time
except KeyboardInterrupt:
    stop(tm)
