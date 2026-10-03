#!/bin/bash
# Opens the Elite Dangerous community page in a kiosk-mode Chromium window.
# Does nothing if Chromium is already running, so it is safe to call from a
# shortcut. Also safe to run from an SSH session.

NEWS_URL="https://community.elitedangerous.com/"

if pgrep -x chromium >/dev/null 2>&1; then
    echo "Chromium is already running."
    exit 0
fi

# Started the same way it was tested by hand (through XWayland)
env -u WAYLAND_DISPLAY DISPLAY=:0 nohup chromium --kiosk --noerrdialogs \
    --disable-infobars --disable-session-crashed-bubble --password-store=basic \
    "$NEWS_URL" >/dev/null 2>&1 &
