#!/bin/bash
# Starts the cyberdeck: the news page in kiosk mode, then the nav computer on top.
#
#   start_deck.sh                      start both windows
#   start_deck.sh --install-autostart  make this run when the desktop starts

NAV_DIR="$HOME/navcomputer"
NEWS_URL="https://community.elitedangerous.com/"
AUTOSTART_FILE="$HOME/.config/autostart/cyberdeck.desktop"

if [ "$1" = "--install-autostart" ]; then
    mkdir -p "$HOME/.config/autostart"
    chmod +x "$NAV_DIR/start_deck.sh" "$NAV_DIR/launch_nav.sh" "$NAV_DIR/launch_news.sh" 2>/dev/null
    cat > "$AUTOSTART_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Cyberdeck
Comment=News page and nav computer
Exec=$NAV_DIR/start_deck.sh
Terminal=false
DESKTOP
    echo "Autostart installed: $AUTOSTART_FILE"
    if grep -qs "xdg-autostart" /etc/xdg/labwc/autostart; then
        echo "Your desktop runs autostart entries, so this should work."
    else
        echo "Could not confirm that your desktop runs autostart entries. If nothing"
        echo "starts after a reboot, tell me what this prints:"
        echo "  cat /etc/xdg/labwc/autostart"
    fi
    command -v foot >/dev/null 2>&1 || echo "Note: foot is not installed (sudo apt install foot). Without it the nav terminal is not fullscreen."
    exit 0
fi

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# Give the network up to 30 seconds to come up so the news page can load
for _ in $(seq 1 30); do
    curl -sI --max-time 2 "$NEWS_URL" >/dev/null 2>&1 && break
    sleep 1
done

"$NAV_DIR/launch_news.sh"
sleep 5   # let the news page open first so the nav computer ends up on top
"$NAV_DIR/launch_nav.sh"
