import signal
import sys
import tm1637
from time import sleep
import counter_link

# TM1637 counter display. Shows jumps remaining while the nav computer has a
# route open (e.g. "0097"), otherwise the Pi CPU temperature (43.6 C ->
# "43:6°"). The module's decimal points aren't wired, so the colon stands in.

CLK, DIO = 17, 27
INTERVAL = 1.0  # seconds between updates
SENSOR = "/sys/class/thermal/thermal_zone0/temp"  # millidegrees C

COLON = 0x80   # MSB of the second digit drives the colon
DEGREE = 0x63  # segments a, b, f, g


def read_temp():
    with open(SENSOR) as f:
        return int(f.read()) / 1000


def show_temp(tm, celsius):
    tenths = min(max(round(celsius * 10), 0), 999)  # 0.0-99.9
    segments = tm.encode_string(f"{tenths:03d}")
    segments[1] |= COLON
    tm.write(segments + bytearray([DEGREE]))


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
        if jumps is None:
            celsius = read_temp()
            show_temp(tm, celsius)
            status = f"{celsius:5.1f} °C"
        else:
            show_jumps(tm, jumps)
            status = f"{jumps:5d} jumps"
        if sys.stdout.isatty():  # stay quiet in the systemd journal
            print(f"\r{status}   ", end="", flush=True)
        sleep(INTERVAL)
except KeyboardInterrupt:
    stop(tm)
