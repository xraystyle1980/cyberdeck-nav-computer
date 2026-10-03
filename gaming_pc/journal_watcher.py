import copy
import glob
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

JOURNAL_DIR = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")),
    "Saved Games", "Frontier Developments", "Elite Dangerous",
)
PORT = 8765

# Shared state, written by the journal reader and read by the web server
state = {
    "current_system": None,
    "max_jump_range": None,
    "last_updated": None,
    "system": None,  # what is known about the system you are in right now
}
state_lock = threading.Lock()


def new_system_record(name, address):
    return {
        "name": name,
        "address": address,
        "honked": False,          # discovery scan done
        "body_count": None,       # total bodies, known after the discovery scan
        "all_bodies_found": False,
        "scanned": {},            # body name -> WasDiscovered (True / False / None)
        "body_ids": {},           # BodyID -> body name
        "bio": {},                # body name -> {"signals", "genuses", "organics"}
    }


def matches_current(event):
    """True if the event belongs to the system we think we are in."""
    rec = state["system"]
    if rec is None:
        return False
    address = event.get("SystemAddress")
    if address is not None and rec["address"] is not None:
        return address == rec["address"]
    name = event.get("StarSystem") or event.get("SystemName")
    if name is not None:
        return name == rec["name"]
    return True


def bio_entry(rec, body):
    return rec["bio"].setdefault(body, {"signals": None, "genuses": [], "organics": {}})


def biological_count(signals):
    for s in signals or []:
        kind = (s.get("Type") or "") + " " + (s.get("Type_Localised") or "")
        if "Biological" in kind:
            return s.get("Count", 0)
    return 0


def public_system(rec):
    """A plain, JSON-friendly copy of the current system's record."""
    if rec is None:
        return None
    bio = []
    for body, info in rec["bio"].items():
        bio.append({
            "body": body,
            "signals": info["signals"],
            "genuses": list(info["genuses"]),
            "organics": [{"species": s, "stage": st} for s, st in info["organics"].items()],
        })
    return {
        "name": rec["name"],
        "honked": rec["honked"],
        "body_count": rec["body_count"],
        "all_bodies_found": rec["all_bodies_found"],
        "bodies_scanned": len(rec["scanned"]),
        "first_discoveries": sum(1 for v in rec["scanned"].values() if v is False),
        "bio": bio,
    }


def snapshot():
    with state_lock:
        out = {k: copy.deepcopy(v) for k, v in state.items() if k != "system"}
        out["system"] = public_system(state["system"])
    return out


STAGES = {"Log": "LOGGED", "Sample": "SAMPLED", "Analyse": "ANALYSED"}


def handle_event(event):
    kind = event.get("event")
    now = time.time()

    if kind in ("FSDJump", "Location", "CarrierJump"):
        name = event.get("StarSystem")
        if name:
            with state_lock:
                state["current_system"] = name
                state["system"] = new_system_record(name, event.get("SystemAddress"))
                state["last_updated"] = now
            print(f"[watcher] Current system: {name}")
        return

    if kind == "Loadout":
        max_range = event.get("MaxJumpRange")
        if max_range:
            with state_lock:
                state["max_jump_range"] = round(max_range, 2)
                state["last_updated"] = now
            print(f"[watcher] Max jump range: {max_range:.2f} LY")
        return

    with state_lock:
        if not matches_current(event):
            return
        rec = state["system"]

        if kind == "FSSDiscoveryScan":
            rec["honked"] = True
            rec["body_count"] = event.get("BodyCount", rec["body_count"])

        elif kind == "FSSAllBodiesFound":
            rec["all_bodies_found"] = True
            if rec["body_count"] is None:
                rec["body_count"] = event.get("Count")

        elif kind == "Scan":
            body = event.get("BodyName")
            # Belt clusters are not counted in the discovery scan's body total
            if body and "Belt Cluster" not in body:
                rec["scanned"][body] = event.get("WasDiscovered")
                if event.get("BodyID") is not None:
                    rec["body_ids"][event["BodyID"]] = body

        elif kind in ("FSSBodySignals", "SAASignalsFound"):
            body = event.get("BodyName")
            if body:
                if event.get("BodyID") is not None:
                    rec["body_ids"][event["BodyID"]] = body
                count = biological_count(event.get("Signals"))
                genuses = [
                    g.get("Genus_Localised") or g.get("Genus")
                    for g in event.get("Genuses", [])
                    if g.get("Genus_Localised") or g.get("Genus")
                ]
                if count > 0 or genuses:
                    entry = bio_entry(rec, body)
                    if count > 0:
                        entry["signals"] = count
                    if genuses:
                        entry["genuses"] = genuses

        elif kind == "ScanOrganic":
            body_id = event.get("Body")
            body = rec["body_ids"].get(body_id, f"BODY {body_id}")
            species = event.get("Species_Localised") or event.get("Genus_Localised") or "UNKNOWN"
            stage = STAGES.get(event.get("ScanType"), str(event.get("ScanType")).upper())
            bio_entry(rec, body)["organics"][species] = stage

        else:
            return

        state["last_updated"] = now


def process_line(line):
    line = line.strip()
    if not line:
        return
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return
    try:
        handle_event(event)
    except Exception as e:  # never let one odd event stop the watcher
        print(f"[watcher] Skipped an event: {e}")


def find_latest_journal():
    files = glob.glob(os.path.join(JOURNAL_DIR, "Journal.*.log"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def tail_journal():
    current_path = None
    f = None
    buffer = ""

    while True:
        if f is None:
            latest = find_latest_journal()
            if latest is None:
                time.sleep(2)
                continue
            current_path = latest
            print(f"[watcher] Watching: {current_path}")
            f = open(current_path, "r", encoding="utf-8", errors="replace")
            buffer = ""

        chunk = f.readline()
        if chunk:
            buffer += chunk
            if buffer.endswith("\n"):  # only handle complete lines
                process_line(buffer)
                buffer = ""
            continue

        # Nothing new: wait, then check whether a newer journal has started
        time.sleep(1)
        latest = find_latest_journal()
        if latest and latest != current_path:
            f.close()
            f = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            body = json.dumps(snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silence default request logging


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[watcher] Serving on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=tail_journal, daemon=True).start()
    run_server()
