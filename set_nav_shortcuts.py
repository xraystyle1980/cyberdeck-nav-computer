#!/usr/bin/env python3
"""
Sets up two labwc shortcuts that jump straight to a window, and start the
program if it is not open:

    Win + Delete   ->  the nav computer window (title contains NAV COMPUTER)
    Win + /        ->  the news page (the kiosk Chromium window)

Safe to run more than once. It backs up your config before changing it, keeps
your existing shortcuts, checks the result is valid XML, and reloads the
desktop. It also replaces the older single Win+Delete toggle if you installed
that one.
"""
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

USER_DIR = os.path.expanduser("~/.config/labwc")
USER_RC = os.path.join(USER_DIR, "rc.xml")
SYSTEM_RC = os.environ.get("LABWC_SYSTEM_RC", "/etc/xdg/labwc/rc.xml")

BEGIN = "<!-- BEGIN nav-computer shortcuts -->"
END = "<!-- END nav-computer shortcuts -->"

NAV_DIR = os.path.expanduser("~/navcomputer")
SCRIPTS = ["start_deck.sh", "launch_nav.sh", "launch_news.sh"]

BLOCK = f"""    {BEGIN}
    <keybind key="W-Delete">
      <action name="ForEach">
        <query title="*NAV COMPUTER*" />
        <then>
          <action name="Raise" />
          <action name="Focus" />
        </then>
        <none>
          <action name="Execute" command="{NAV_DIR}/launch_nav.sh" />
        </none>
      </action>
    </keybind>
    <keybind key="W-slash">
      <action name="ForEach">
        <query identifier="*chromium*" />
        <then>
          <action name="Raise" />
          <action name="Focus" />
        </then>
        <none>
          <action name="Execute" command="{NAV_DIR}/launch_news.sh" />
        </none>
      </action>
    </keybind>
    {END}
"""

MINIMAL = """<?xml version="1.0"?>
<labwc_config>
  <keyboard>
    <default />
  </keyboard>
</labwc_config>
"""

# The single Win+Delete toggle written by the earlier add_nav_toggle.py
LEGACY = re.compile(
    r'[ \t]*<keybind key="W-Delete">\s*<action name="NextWindow" />\s*</keybind>[ \t]*\n?'
)
OURS = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"[ \t]*\n?", flags=re.S)
OURS_LINE = re.compile(r"[ \t]*" + re.escape(BEGIN))  # leading indent of our block


def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def remove_ours(text):
    """Removes our own block and the older toggle, leaving everything else."""
    text = OURS_LINE.sub(BEGIN, text)
    text = OURS.sub("", text)
    text = LEGACY.sub("", text)
    return text


def add_block(text):
    selfclosing = re.search(r"<keyboard\b[^>]*/>", text)
    block = re.search(r"(<keyboard\b[^>]*>)(.*?)(</keyboard>)", text, flags=re.S)

    if selfclosing and not block:
        new = "<keyboard>\n    <default />\n" + BLOCK + "  </keyboard>"
        return text[:selfclosing.start()] + new + text[selfclosing.end():]

    if block:
        inner = block.group(2)
        clean = strip_comments(inner)
        # With no keybinds at all labwc quietly loads its defaults. Adding ours
        # would switch that off, so add <default /> to keep them.
        need_default = "<default" not in clean and "<keybind" not in clean
        addition = ("    <default />\n" if need_default else "") + BLOCK
        new_inner = inner.rstrip(" \n") + "\n" + addition + "  "
        return text[:block.start(2)] + new_inner + text[block.end(2):]

    end = max(text.rfind("</labwc_config>"), text.rfind("</openbox_config>"))
    if end == -1:
        raise ValueError(
            "could not find the closing </labwc_config> or </openbox_config> tag "
            "at the end of the file"
        )
    new = "  <keyboard>\n    <default />\n" + BLOCK + "  </keyboard>\n"
    return text[:end] + new + text[end:]


def prepare_scripts():
    for name in SCRIPTS:
        path = os.path.join(NAV_DIR, name)
        if os.path.exists(path):
            os.chmod(path, 0o755)
        else:
            print(f"Note: {path} is missing. Copy it over or the shortcut that uses it will do nothing.")


def main():
    prepare_scripts()
    os.makedirs(USER_DIR, exist_ok=True)

    if not os.path.exists(USER_RC):
        if os.path.exists(SYSTEM_RC):
            shutil.copy(SYSTEM_RC, USER_RC)
            print(f"Copied the system config to {USER_RC} so nothing in it is lost.")
        else:
            with open(USER_RC, "w", encoding="utf-8") as f:
                f.write(MINIMAL)
            print(f"No config found, so created a minimal one at {USER_RC}.")

    with open(USER_RC, "rb") as f:
        original = f.read().decode("utf-8")

    cleaned = remove_ours(original)

    # If something else already uses these keys, stop rather than create a clash
    visible = strip_comments(cleaned)
    for key in ("W-Delete", "W-slash", "W-/"):
        if f'key="{key}"' in visible:
            print(f'Stopped without changing anything: {key} is already used by another '
                  f"shortcut in {USER_RC}. Tell me and we will pick different keys.")
            return 1

    try:
        updated = add_block(cleaned)
        ET.fromstring(updated.encode("utf-8"))  # must still be valid XML
    except (ValueError, ET.ParseError) as e:
        print(f"Stopped without changing anything: {e}")
        return 1

    if updated == original:
        print("The shortcuts are already set up. Nothing to change.")
        return 0

    backup = f"{USER_RC}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy(USER_RC, backup)
    with open(USER_RC, "w", encoding="utf-8") as f:
        f.write(updated)
    print("Shortcuts set:")
    print("  Win + Delete  ->  nav computer window")
    print("  Win + /       ->  news page window")
    print(f"Backup of your old config: {backup}")

    try:
        result = subprocess.run(["pkill", "-HUP", "-x", "labwc"])
        if result.returncode == 0:
            print("Reloaded the desktop. Try them now.")
        else:
            print("Could not find a running labwc to reload. Log out and back in, or reboot.")
    except FileNotFoundError:
        print("Could not reload automatically. Log out and back in, or reboot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
