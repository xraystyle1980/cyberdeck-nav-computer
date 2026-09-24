# Cyberdeck Nav Computer

A Raspberry Pi 5 cyberdeck running an Elite Dangerous navigation terminal,
with a TM1637 7-segment counter on the GPIO header.

- **Nav computer** (`nav_computer.py`): full-screen terminal UI that plots
  neutron-star routes through the [Spansh](https://spansh.co.uk) API.
  Start and destination names are checked against Spansh's system list,
  with suggestions for partial names.
- **Counter display**: shows the Pi's CPU temperature (`43:6°` = 43.6 °C;
  the module's decimal points aren't wired, so the colon stands in) or the
  live download rate.

## Hardware

| Part | Notes |
|---|---|
| Raspberry Pi 5 | Raspberry Pi OS (Debian trixie), labwc/Wayland, LightDM autologin |
| MPI7002 7" HDMI touchscreen | Touch over USB; the screen itself is USB-powered |
| Corne v4.1 split keyboard | Vial firmware, wired USB |
| TM1637 4-digit display | CLK → GPIO 17, DIO → GPIO 27; colon only, no decimal points |
| Active cooler | Pi 5 default fan curve (on at 50 °C) |

## Setup

```bash
git clone git@github.com:xraystyle1980/cyberdeck-nav-computer.git ~/navcomputer
cd ~/navcomputer
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Run it: `venv/bin/python nav_computer.py`

### Desktop integration

Paths in these files assume the user `lonestarr` and `~/navcomputer`.

```bash
# Counter display at boot (temperature; live-rate is the alternative)
cp system/systemd-user/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now temp-display
sudo loginctl enable-linger "$USER"   # start user services at boot

# Nav Computer launcher: app menu, desktop and taskbar
cp system/applications/nav-computer.desktop ~/.local/share/applications/
cp system/applications/nav-computer.desktop ~/Desktop/
gio set ~/Desktop/nav-computer.desktop metadata::trusted true
# then add "nav-computer" to launchers= in ~/.config/wf-panel-pi/wf-panel-pi.ini

# Open Nav Computer full screen (merge into ~/.config/labwc/rc.xml)
cp system/labwc/rc.xml ~/.config/labwc/rc.xml
```

Switch the counter between readouts (each stops the other):

```bash
systemctl --user start live-rate      # download rate: KB/s, colon lit = MB/s
systemctl --user start temp-display   # CPU temperature
```

### Keyboard cold-boot fix

On a cold boot the Corne powers up while the Pi's USB is still in early
boot, and it stays unresponsive until replugged (it enumerates, but sends
no key events; re-enumerating doesn't help). This service cuts USB power
once Linux is up so the keyboard restarts with the host ready.

Pi 5 USB port power is ganged, so all four root hubs are switched together,
which also blanks the USB-powered screen. The service therefore runs before
LightDM and waits for HDMI to reconnect; cutting it with the desktop running
crashes labwc.

```bash
sudo apt install uhubctl
sudo install -m 755 system/usb-power-cycle.sh /usr/local/sbin/
sudo install -m 644 system/systemd/usb-power-cycle.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable usb-power-cycle
```

## Other scripts

- `test_display.py`: random numbers on the counter (stop the display service first)
- `heat_test.sh [seconds]`: loads all cores and prints temperature and fan speed

## Notes

- **Don't `apt remove gnome-keyring`** on Raspberry Pi OS: it also removes
  `rpd-wayland-core`, `rpd-common` and `rpd-x-core`, which breaks the
  desktop session ("Failed to start session"). To silence keyring prompts,
  mask it instead: comment out `pam_gnome_keyring.so` in `/etc/pam.d/lightdm`
  and override its D-Bus services in `~/.local/share/dbus-1/services/` with
  `Exec=/bin/false`.
- **Wallpaper resets**: pcmanfm stores the wallpaper per output name. If the
  screen isn't detected at login, the desktop comes up as `NOOP-1`, so keep
  `desktop-items-NOOP-1.conf` and `desktop-items-HDMI-A-1.conf` in sync.
