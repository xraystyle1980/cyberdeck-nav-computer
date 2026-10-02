import tm1637
import time
from datetime import datetime

tm = tm1637.TM1637(clk=17, dio=27)
tm.brightness(7)

try:
    while True:
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        colon_on = now.second % 2 == 0  # blink colon every other second

        tm.numbers(hour, minute, colon=colon_on)
        time.sleep(1)
except KeyboardInterrupt:
    tm.show("    ")
    print("\nStopped — display cleared.")
