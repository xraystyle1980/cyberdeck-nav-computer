#!/bin/bash
# Opens the nav computer in a fullscreen terminal on the Pi's own screen.
# Does nothing if the nav computer is already running, so it is safe to call
# from a shortcut. Also safe to run from an SSH session.

if pgrep -f "python3 nav_computer.py" >/dev/null 2>&1; then
    echo "The nav computer is already running."
    exit 0
fi

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

NAV_CMD='cd "$HOME/navcomputer" && source venv/bin/activate && python3 nav_computer.py'

if command -v foot >/dev/null 2>&1; then
    # foot starts fullscreen with no menu bar or scrollbar. Raise or lower the
    # font size number to taste.
    nohup foot --fullscreen --title="NAV COMPUTER" --app-id=navcomputer \
        --font="monospace:size=12" bash -c "$NAV_CMD" >/dev/null 2>&1 &
elif command -v lxterminal >/dev/null 2>&1; then
    # Fallback: press F11 in the window to make it fullscreen
    nohup lxterminal --title="NAV COMPUTER" -e bash -c "$NAV_CMD" >/dev/null 2>&1 &
else
    echo "No terminal found. Try: sudo apt install foot"
    exit 1
fi
