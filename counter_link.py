import json
import os

# Shared with counter_display.py. Lives in the runtime dir (RAM, cleared on
# reboot), so frequent updates don't wear the SD card.
STATE_FILE = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "nav-computer-counter.json")


def show_jumps(jumps_remaining):
    """Ask the counter display to show jumps remaining instead of the temperature."""
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        # The PID lets the display ignore this file if the nav computer dies
        json.dump({"jumps_remaining": jumps_remaining, "pid": os.getpid()}, f)
    os.replace(tmp, STATE_FILE)


def clear():
    """Hand the counter display back to the temperature."""
    try:
        os.remove(STATE_FILE)
    except FileNotFoundError:
        pass


def read():
    """Jumps remaining if a live nav computer has asked to show them, else None."""
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        os.kill(state["pid"], 0)  # raises if that process no longer exists
        return int(state["jumps_remaining"])
    except ProcessLookupError:
        return None
    except PermissionError:
        return int(state["jumps_remaining"])  # process exists, owned by someone else
    except (OSError, ValueError, KeyError, TypeError):
        return None
