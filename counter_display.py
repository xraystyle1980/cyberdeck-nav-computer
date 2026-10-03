import signal
import sys
import tm1637
from datetime import datetime
from time import sleep
import counter_link

# TM1637 display. Shows jumps remaining while the nav computer has a route
# open (e.g. "0097"), otherwise the time in 24 hour format with a blinking colon.

CLK, DIO = 17, 27
INTERVAL = 1.0  # seconds between updates


def show_jumps(tm, jumps):
    tm.show(f"{min(max(jumps, 0), 9999):04d}")


def show_time(tm, now):
    tm.numbers(now.hour, now.minute, colon=(now.second % 2 == 0))


def render(tm, jumps, now):
    """Draws one frame and returns a short text description of it."""
    if jumps is not None:
        show_jumps(tm, jumps)
        return f"{jumps:5d} jumps"
    show_time(tm, now)
    return now.strftime("%H:%M")


def stop(tm):
    tm.show("    ")
    print("\nStopped - display cleared.")
    sys.exit(0)


def main():
    tm = tm1637.TM1637(clk=CLK, dio=DIO)
    tm.brightness(7)
    signal.signal(signal.SIGTERM, lambda *_: stop(tm))

    try:
        while True:
            status = render(tm, counter_link.read(), datetime.now())
            if sys.stdout.isatty():  # stay quiet in the systemd journal
                print(f"\r{status}   ", end="", flush=True)
            sleep(INTERVAL)
    except KeyboardInterrupt:
        stop(tm)


if __name__ == "__main__":
    main()
