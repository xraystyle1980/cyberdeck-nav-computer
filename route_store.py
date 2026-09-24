import json
import os
from datetime import datetime

# Saved routes live outside the repo: they're personal data, not code.
ROUTES_DIR = os.path.expanduser("~/.local/share/nav-computer/routes")


def _path(route):
    return os.path.join(ROUTES_DIR, route["id"] + ".json")


def save(route):
    """Write atomically so a power cut mid-save can't corrupt a route."""
    os.makedirs(ROUTES_DIR, exist_ok=True)
    path = _path(route)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(route, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def create(plot):
    """Save a freshly plotted route (from spansh_client) and return it."""
    now = datetime.now()
    route = dict(plot)
    route.update({
        "id": now.strftime("%Y%m%d-%H%M%S"),
        "created": now.strftime("%Y-%m-%d %H:%M"),
        "status": "active",
        "position": 0,  # index of the waypoint you're currently at
        "completed": None,
    })
    save(route)
    return route


def load_all():
    """All saved routes: active first, then newest first."""
    routes = []
    if os.path.isdir(ROUTES_DIR):
        for name in os.listdir(ROUTES_DIR):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(ROUTES_DIR, name)) as f:
                    routes.append(json.load(f))
            except (OSError, ValueError):
                continue  # skip unreadable files rather than crash the UI
    routes.sort(key=lambda r: r["id"], reverse=True)
    routes.sort(key=lambda r: r["status"] != "active")
    return routes


def delete(route):
    os.remove(_path(route))


def set_position(route, position):
    last = len(route["waypoints"]) - 1
    route["position"] = max(0, min(position, last))
    if route["position"] == last:
        mark_complete(route)
    else:
        save(route)


def mark_complete(route):
    route["status"] = "completed"
    route["completed"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save(route)


def reopen(route):
    route["status"] = "active"
    route["completed"] = None
    save(route)


def jumps_remaining(route):
    return sum(w["jumps"] for w in route["waypoints"][route["position"] + 1:])


def total_jumps(route):
    return sum(w["jumps"] for w in route["waypoints"])
