import time
import psutil
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306

serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, width=128, height=64)
device.contrast(255)

NAV_VERSION = "v0.2"
SPANSH_STATUS = "OK"  # placeholder — wire to real check later

def get_cpu_temp():
    temps = psutil.sensors_temperatures()
    if 'cpu_thermal' in temps:
        return temps['cpu_thermal'][0].current
    return None

try:
    while True:
        temp = get_cpu_temp()
        temp_str = f"{temp:.1f}C" if temp is not None else "N/A"

        with canvas(device) as draw:
            # Yellow zone (top ~16px) — header
            draw.text((2, 2), "SYSTEM", fill="white")

            # Blue zone — live data
            draw.text((2, 20), f"CPU Temp: {temp_str}", fill="white")
            draw.text((2, 32), f"Nav Version: {NAV_VERSION}", fill="white")
            draw.text((2, 44), f"Spansh API: {SPANSH_STATUS}", fill="white")

        time.sleep(2)  # refresh every 2 seconds

except KeyboardInterrupt:
    device.clear()
    print("\nStopped — display cleared.")
