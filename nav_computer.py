import os
import sys
import json
import time
import select
import threading
import itertools
import subprocess
from datetime import datetime
from spansh_client import plot_neutron_route, lookup_system
from game_link import get_game_state
import counter_link

GREEN = "\033[32m"
BRIGHT = "\033[92m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

WIDTH = 78
POLL_SECONDS = 2.5
ROUTE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_route.json")

def clear():
    print(CLEAR, end="")

def border_top():
    print(BRIGHT + "┌" + "─" * (WIDTH - 2) + "┐" + RESET)

def border_bottom():
    print(BRIGHT + "└" + "─" * (WIDTH - 2) + "┘" + RESET)

def rule():
    print(BRIGHT + "├" + "─" * (WIDTH - 2) + "┤" + RESET)

def line(text=""):
    inner = WIDTH - 4
    print(BRIGHT + "│ " + text[:inner].ljust(inner) + " │" + RESET)

def blank():
    line("")

SOLAR_SYSTEM_EMBLEM = [
    "                              .       *           .          ",
    "          *          .                    .                  ",
    "   .                                              *          ",
    "                                                              ",
    "     \\ | /                                                   ",
    "   -- (@) --   o    O     O     o      ( O )     O       O   o",
    "     / | \\                                            / \\     ",
    "      SOL                  /                                 ",
    "                          .                                   ",
    "                                                              ",
    "   .          *                   .            *           . ",
]

BANNER_TITLE = [
    " N A V   C O M P U T E R",
    " FSD NAVIGATION INTERFACE v0.3",
]

def enter_nav_mode():
    subprocess.run(["systemctl", "--user", "stop", "clock-display.service"])
    subprocess.run(["systemctl", "--user", "start", "counter-display.service"])

def exit_nav_mode():
    counter_link.clear()
    subprocess.run(["systemctl", "--user", "stop", "counter-display.service"])
    subprocess.run(["systemctl", "--user", "start", "clock-display.service"])

def run_with_spinner(label, func, *args, **kwargs):
    spinner_chars = itertools.cycle(['|', '/', '-', '\\'])
    stop_event = threading.Event()
    result_holder = {}
    error_holder = {}

    def worker():
        try:
            result_holder['result'] = func(*args, **kwargs)
        except Exception as e:
            error_holder['error'] = e
        finally:
            stop_event.set()

    thread = threading.Thread(target=worker)
    thread.start()

    while not stop_event.is_set():
        sys.stdout.write(f"\r{BRIGHT}  {label} {next(spinner_chars)}{RESET}")
        sys.stdout.flush()
        time.sleep(0.1)

    thread.join()
    sys.stdout.write("\r" + " " * (len(label) + 4) + "\r")
    sys.stdout.flush()

    if 'error' in error_holder:
        raise error_holder['error']
    return result_holder['result']

def confirm_system(entered_name):
    exact_name, suggestions = run_with_spinner("SEARCHING", lookup_system, entered_name)
    if exact_name:
        return exact_name
    if suggestions:
        print(BRIGHT + f"\n  NO EXACT MATCH FOR '{entered_name}'. CLOSEST MATCHES:" + RESET)
        for i, s in enumerate(suggestions, start=1):
            line(f"  [{i}] {s}")
        choice = input(GREEN + "\n  SELECT A NUMBER, OR PRESS ENTER TO KEEP TYPED NAME > " + RESET).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(suggestions):
            return suggestions[int(choice) - 1]
    return entered_name

# --- Route persistence ---

def save_route(source, dest, jump_range, waypoints, current_index, jumps_done=0):
    data = {
        "source": source,
        "destination": dest,
        "jump_range": jump_range,
        "waypoints": waypoints,
        "current_index": current_index,
        "jumps_done": jumps_done,
        "saved_at": datetime.now().isoformat(),
    }
    tmp = ROUTE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, ROUTE_FILE)

def load_route():
    if not os.path.exists(ROUTE_FILE):
        return None
    try:
        with open(ROUTE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

def clear_route():
    try:
        os.remove(ROUTE_FILE)
    except FileNotFoundError:
        pass

# --- Route counting ---
# Spansh returns one entry per neutron stop. Each entry's "jumps" is the number
# of jumps needed to reach that stop from the previous one. The first entry is
# the starting system (0 jumps).

def drop_start(waypoints):
    """Remove the starting system, which is not somewhere you still need to go."""
    if waypoints and waypoints[0].get("jumps", 0) == 0:
        return waypoints[1:]
    return waypoints

def jumps_remaining(legs, idx, done):
    """Jumps left: the unfinished part of the current leg plus every later leg."""
    if idx >= len(legs):
        return 0
    current = max(legs[idx]["jumps"] - done, 0)
    later = sum(leg["jumps"] for leg in legs[idx + 1:])
    return current + later

def manual_jump(legs, idx, done):
    """One manual jump. Finishing the leg's last jump means you reached the stop."""
    done += 1
    if done >= legs[idx]["jumps"]:
        return idx + 1, 0
    return idx, done

def sync_with_game(legs, idx, done, new_system):
    """
    Called when the game's current system changes.
    Reaching the current stop moves on one leg, reaching a later stop skips
    ahead, and anywhere else counts as one jump along the current leg.
    Returns (idx, done, note).
    """
    for i in range(idx, len(legs)):
        if legs[i]["system"].lower() == new_system.lower():
            note = f"[SYNC] SKIPPED AHEAD TO {legs[i]['system']}" if i > idx else ""
            return i + 1, 0, note
    return idx, done + 1, ""

def key_pressed(timeout=POLL_SECONDS):
    """Returns the typed line if one arrives within the timeout, otherwise None."""
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    text = sys.stdin.readline()
    if text == "":
        raise EOFError  # terminal went away
    return text.strip().lower()

# --- Jump tracking screen ---

def draw_tracker(source, dest, legs, idx, done, remaining, link_text, note):
    stop = legs[idx]
    clear()
    border_top()
    line("ROUTE IN PROGRESS")
    rule()
    blank()
    line(f"  {source.upper()} -> {dest.upper()}")
    line(f"  STOP {idx + 1} OF {len(legs)}        JUMPS REMAINING: {remaining}")
    blank()
    tag = "* NEUTRON BOOST" if stop["neutron_star"] else ""
    line(f"  NEXT: {stop['system']} {tag}")
    line(f"  THIS LEG: {min(done, stop['jumps'])} OF {stop['jumps']} JUMPS")
    blank()
    line(f"  GAME LINK: {link_text}")
    if note:
        line(f"  {note}")
    blank()
    line("[ENTER] +1 JUMP  [N] STOP REACHED  [S] SAVE & EXIT  [Q] ABANDON")
    border_bottom()

def run_jump_tracker(source, dest, jump_range, legs, idx, done=0):
    note = ""
    link_text = "OFFLINE (MANUAL ONLY)"
    last_system = None
    try:
        state = get_game_state()
        if state and state.get("current_system"):
            last_system = state["current_system"]
            link_text = f"ONLINE - IN {last_system.upper()}"

        while idx < len(legs):
            remaining = jumps_remaining(legs, idx, done)
            counter_link.show_jumps(remaining)
            draw_tracker(source, dest, legs, idx, done, remaining, link_text, note)

            choice = key_pressed()

            if choice is not None:
                if choice == "":
                    idx, done = manual_jump(legs, idx, done)
                    note = ""
                elif choice == "n":
                    idx, done = idx + 1, 0
                    note = ""
                elif choice == "s":
                    save_route(source, dest, jump_range, legs, idx, done)
                    counter_link.clear()
                    print(BRIGHT + "\n  ROUTE SAVED - RETURNING TO MENU\n" + RESET)
                    input(GREEN + "  PRESS ENTER..." + RESET)
                    return
                elif choice == "q":
                    clear_route()
                    counter_link.clear()
                    print(BRIGHT + "\n  ROUTE ABANDONED\n" + RESET)
                    input(GREEN + "  PRESS ENTER..." + RESET)
                    return
                save_route(source, dest, jump_range, legs, idx, done)
                continue

            # No key pressed: look at the game
            state = get_game_state()
            system = state.get("current_system") if state else None
            if system:
                link_text = f"ONLINE - IN {system.upper()}"
                if last_system is not None and system != last_system:
                    idx, done, note = sync_with_game(legs, idx, done, system)
                    save_route(source, dest, jump_range, legs, idx, done)
                last_system = system
            else:
                link_text = "OFFLINE (MANUAL ONLY)"

        clear_route()
        counter_link.clear()
        clear()
        border_top()
        line("ROUTE COMPLETE")
        rule()
        blank()
        line(f"  ARRIVED AT {dest.upper()}")
        blank()
        border_bottom()
        input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)
    except (KeyboardInterrupt, EOFError):
        save_route(source, dest, jump_range, legs, idx, done)
        counter_link.clear()

def draw_main_menu(has_saved_route):
    clear()
    border_top()
    blank()
    for l in SOLAR_SYSTEM_EMBLEM:
        line(l)
    blank()
    for l in BANNER_TITLE:
        line(l)
    rule()
    blank()
    line("[1] NEUTRON ROUTE")
    line("[2] STANDARD ROUTE")
    line("[3] SYSTEM INFO")
    if has_saved_route:
        line("[4] RESUME ROUTE")
    line("[Q] QUIT")
    blank()
    border_bottom()

def ask_current_system(state):
    """
    Asks for the starting system.
    Watcher running: Enter takes the game's current system.
    Watcher not running: Enter explains why, then asks again, so you can type a
    system by hand or start the watcher and press Enter once more.
    Returns the system name, or None if the user types MENU to go back.
    """
    notice = ""
    while True:
        game_system = state.get("current_system") if state else None
        if notice:
            print(BRIGHT + notice + RESET)
        if game_system:
            prompt = f"\n  CURRENT SYSTEM [{game_system}] > "
        elif state is None:
            prompt = "\n  CURRENT SYSTEM (WATCHER OFFLINE) > "
        else:
            prompt = "\n  CURRENT SYSTEM > "
        typed = input(GREEN + prompt + RESET).strip()
        if typed.lower() == "menu":
            return None
        if typed:
            return typed
        if game_system:
            return game_system
        if state is None:
            notice = ("  WATCHER NOT RUNNING. START IT ON THE GAMING PC, OR TYPE A SYSTEM.\n"
                      "  (TYPE MENU TO GO BACK)")
        else:
            notice = ("  WATCHER RUNNING, BUT NO SYSTEM REPORTED YET. TYPE A SYSTEM.\n"
                      "  (TYPE MENU TO GO BACK)")
        state = get_game_state()  # re-check, in case the watcher was just started

def ask_jump_range(state):
    """
    Asks for the jump range in light years.
    Watcher reporting a range: Enter takes it.
    Otherwise Enter explains why, then asks again so you can type one.
    Returns a float, or None if the user types MENU to go back.
    """
    notice = ""
    while True:
        game_range = state.get("max_jump_range") if state else None
        if notice:
            print(BRIGHT + notice + RESET)
        if game_range:
            prompt = f"  JUMP RANGE (LY) [{game_range}] > "
        elif state is None:
            prompt = "  JUMP RANGE (LY) (WATCHER OFFLINE) > "
        else:
            prompt = "  JUMP RANGE (LY) > "
        typed = input(GREEN + prompt + RESET).strip()
        if typed.lower() == "menu":
            return None
        if typed == "":
            if game_range:
                return float(game_range)
            if state is None:
                notice = ("  WATCHER NOT RUNNING. TYPE YOUR JUMP RANGE, OR START THE WATCHER.\n"
                          "  (TYPE MENU TO GO BACK)")
            else:
                notice = ("  WATCHER HAS NO JUMP RANGE YET. TYPE ONE.\n"
                          "  (TYPE MENU TO GO BACK)")
            state = get_game_state()  # re-check, in case the watcher was just started
            continue
        try:
            value = float(typed)
        except ValueError:
            notice = "  ENTER THE RANGE AS A NUMBER, LIKE 48.2"
            continue
        if value <= 0:
            notice = "  THE RANGE MUST BE GREATER THAN ZERO."
            continue
        return value

def neutron_route():
    clear()
    border_top()
    line("NEUTRON ROUTE PLOTTER")
    rule()

    state = get_game_state()

    source_raw = ask_current_system(state)
    if source_raw is None:
        return
    source = confirm_system(source_raw)

    dest_raw = input(GREEN + "  DESTINATION SYSTEM > " + RESET).strip()
    if not dest_raw:
        print(BRIGHT + "\n  [NO DESTINATION GIVEN]\n" + RESET)
        input(GREEN + "  PRESS ENTER TO RETURN..." + RESET)
        return
    dest = confirm_system(dest_raw)

    jump_range = ask_jump_range(state)
    if jump_range is None:
        return

    try:
        result = run_with_spinner(
            "PLOTTING ROUTE",
            plot_neutron_route,
            source, dest, jump_range=jump_range
        )
        legs = drop_start(result.get("waypoints", []))
        if not legs:
            print(BRIGHT + "\n  [NO ROUTE RETURNED]\n" + RESET)
            input(GREEN + "  PRESS ENTER TO RETURN..." + RESET)
            return

        total_jumps = sum(leg["jumps"] for leg in legs)
        print(BRIGHT + f"\n  ROUTE FOUND - {len(legs)} STOPS, {total_jumps} JUMPS\n" + RESET)
        for stop in legs[:10]:
            tag = "* NEUTRON" if stop["neutron_star"] else ""
            line(f"  {stop['system']}  ({stop['jumps']} JUMPS) {tag}")
        input(GREEN + "\n  PRESS ENTER TO BEGIN ROUTE..." + RESET)

        save_route(source, dest, jump_range, legs, 0, 0)
        run_jump_tracker(source, dest, jump_range, legs, 0, 0)

    except Exception as e:
        print(BRIGHT + f"\n  [ERROR: {e}]\n" + RESET)
        input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)

def resume_route():
    saved = load_route()
    if saved is None:
        clear()
        border_top()
        line("NO SAVED ROUTE FOUND")
        border_bottom()
        input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)
        return
    legs = saved["waypoints"]
    idx = saved["current_index"]
    if idx == 0:
        legs = drop_start(legs)  # older saves still include the starting system
    run_jump_tracker(
        saved["source"], saved["destination"], saved["jump_range"],
        legs, idx, saved.get("jumps_done", 0)
    )

def standard_route():
    clear()
    border_top()
    line("STANDARD ROUTE PLOTTER")
    rule()
    input(GREEN + "\n  DESTINATION SYSTEM > " + RESET)
    print(BRIGHT + "\n  [FEATURE NOT YET IMPLEMENTED]\n" + RESET)
    input(GREEN + "  PRESS ENTER TO RETURN..." + RESET)

def short_body(body, system_name):
    """Drops the system name from the front of a body name: 'Sol 3' -> '3'."""
    prefix = (system_name or "") + " "
    if system_name and body.lower().startswith(prefix.lower()):
        return body[len(prefix):]
    return body

def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "S")

def system_info_lines(state):
    """Builds the text of the SYSTEM INFO screen from the watcher's status."""
    if "system" not in state:
        return ["", "  THE WATCHER IS OUT OF DATE (NO SYSTEM DATA).",
                "  RESTART IT WITH THE UPDATED journal_watcher.py."]
    system = state.get("system")
    if not system:
        return ["", "  NO SYSTEM REPORTED YET."]

    name = system.get("name", "UNKNOWN")
    out = ["", f"  SYSTEM: {name.upper()}"]
    ship_range = state.get("max_jump_range")
    if ship_range:
        out.append(f"  SHIP JUMP RANGE: {ship_range} LY")
    out.append("")

    if system.get("all_bodies_found"):
        status = "ALL BODIES FOUND"
    elif system.get("honked"):
        status = "DISCOVERY SCAN DONE, NOT FULLY SCANNED"
    else:
        status = "NOT SCANNED - NO DISCOVERY SCAN YET"
    out.append(f"  SCAN STATUS: {status}")

    scanned = system.get("bodies_scanned", 0)
    total = system.get("body_count")
    out.append(f"  BODIES SCANNED: {scanned} / {total if total is not None else '?'}")
    if scanned:
        out.append(f"  FIRST DISCOVERIES: {system.get('first_discoveries', 0)}")
    out.append("")

    bio = system.get("bio", [])
    if not bio:
        out.append("  EXOBIOLOGY: " + ("NONE" if system.get("all_bodies_found") else "NONE DETECTED SO FAR"))
    else:
        out.append(f"  EXOBIOLOGY: LIFE ON {plural(len(bio), 'BODY').replace('BODYS', 'BODIES')}")
        for entry in bio[:6]:
            signals = entry.get("signals")
            signal_text = plural(signals, "SIGNAL") if signals else "SIGNALS ?"
            genuses = ", ".join(entry.get("genuses") or [])
            text = f"    {short_body(entry['body'], name)}: {signal_text}"
            if genuses:
                text += f" - {genuses}"
            out.append(text)
            for organic in entry.get("organics", []):
                out.append(f"      {organic['species']} ({organic['stage']})")
        if len(bio) > 6:
            out.append(f"    +{len(bio) - 6} MORE")
    out.append("")
    out.append("  SOURCE: THIS SESSION'S JOURNAL ONLY")
    return out

def system_info():
    clear()
    border_top()
    line("SYSTEM INFO")
    rule()
    state = get_game_state()
    if state is None:
        text = ["", "  GAME LINK OFFLINE. START THE WATCHER ON THE GAMING PC."]
    else:
        text = system_info_lines(state)
    for entry in text:
        line(entry)
    blank()
    border_bottom()
    input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)

def main():
    enter_nav_mode()
    try:
        while True:
            has_saved = load_route() is not None
            draw_main_menu(has_saved)
            choice = input(GREEN + "  > " + RESET).strip().lower()
            if choice == "1":
                neutron_route()
            elif choice == "2":
                standard_route()
            elif choice == "3":
                system_info()
            elif choice == "4" and has_saved:
                resume_route()
            elif choice == "q":
                exit_nav_mode()
                clear()
                print(BRIGHT + "NAV COMPUTER OFFLINE.\n" + RESET)
                sys.exit(0)
    except KeyboardInterrupt:
        exit_nav_mode()
        clear()
        print(BRIGHT + "\nNAV COMPUTER OFFLINE (interrupted).\n" + RESET)
        sys.exit(0)

if __name__ == "__main__":
    main()
