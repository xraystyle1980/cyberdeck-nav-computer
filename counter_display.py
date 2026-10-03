import signal
import sys
import tm1637
from time import sleep
import counter_link

# TM1637 counter display. Shows jumps remaining while the nav computer has a
# route open (e.g. "0097"). When no route is active, this script leaves the
# display alone — clock-display.service owns the screen in that state.

CLK, DIO = 17, 27
INTERVAL = 1.0  # seconds between updates


def show_jumps(tm, jumps):
    tm.show(f"{min(max(jumps, 0), 9999):04d}")


def stop(tm):
    tm.show("    ")
    print("\nStopped — display cleared.")
    sys.exit(0)


tm = tm1637.TM1637(clk=CLK, dio=DIO)
tm.brightness(7)
signal.signal(signal.SIGTERM, lambda *_: stop(tm))

try:
    while True:
        jumps = counter_link.read()
        if jumps is not None:
            show_jumps(tm, jumps)
            status = f"{jumps:5d} jumps"
        else:
            status = "idle (no route)"
        if sys.stdout.isatty():  # stay quiet in the systemd journal
            print(f"\r{status}   ", end="", flush=True)
        sleep(INTERVAL)
except KeyboardInterrupt:
    stop(tm)
