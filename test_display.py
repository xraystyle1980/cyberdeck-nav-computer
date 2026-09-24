import tm1637
import random
from time import sleep

tm = tm1637.TM1637(clk=17, dio=27)
tm.brightness(7)

try:
    while True:
        num = random.randint(0, 9999)
        display_str = f"{num:04d}"
        tm.show(display_str)
        print(f"Displaying: {display_str}")
        sleep(60)
except KeyboardInterrupt:
    tm.show("    ")
    print("\nStopped — display cleared.")
