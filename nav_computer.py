import os
import sys
import json
import time
import threading
import itertools
import subprocess
from datetime import datetime
from spansh_client import plot_neutron_route, lookup_system
import counter_link

GREEN = "\033[32m"
BRIGHT = "\033[92m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

WIDTH = 78
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
    print(BRIGHT + "│ " + text.ljust(WIDTH - 4) + " │" + RESET)

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
    " FSD NAVIGATION INTERFACE v0.2",
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

def save_route(source, dest, jump_range, waypoints, current_index):
    data = {
        "source": source,
        "destination": dest,
        "jump_range": jump_range,
        "waypoints": waypoints,
        "current_index": current_index,
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

# --- Jump tracking screen ---

def run_jump_tracker(source, dest, jump_range, waypoints, current_index):
    total = len(waypoints)
    try:
        while current_index < total:
            remaining = total - current_index
            counter_link.show_jumps(remaining)

            clear()
            border_top()
            line("ROUTE IN PROGRESS")
            rule()
            blank()
            line(f"  {source.upper()} -> {dest.upper()}")
            line(f"  JUMP {current_index + 1} OF {total}  ({remaining} REMAINING)")
            blank()
            stop = waypoints[current_index]
            tag = "* NEUTRON BOOST" if stop["neutron_star"] else ""
            line(f"  NEXT: {stop['system']} {tag}")
            blank()
            line("[ENTER] MARK JUMP COMPLETE   [S] SAVE & EXIT   [Q] ABANDON ROUTE")
            border_bottom()

            choice = input(GREEN + "\n  > " + RESET).strip().lower()
            if choice == "":
                current_index += 1
                save_route(source, dest, jump_range, waypoints, current_index)
            elif choice == "s":
                save_route(source, dest, jump_range, waypoints, current_index)
                print(BRIGHT + "\n  ROUTE SAVED — RETURNING TO MENU\n" + RESET)
                input(GREEN + "  PRESS ENTER..." + RESET)
                return
            elif choice == "q":
                clear_route()
                counter_link.clear()
                print(BRIGHT + "\n  ROUTE ABANDONED\n" + RESET)
                input(GREEN + "  PRESS ENTER..." + RESET)
                return

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
    except KeyboardInterrupt:
        save_route(source, dest, jump_range, waypoints, current_index)
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

def neutron_route():
    clear()
    border_top()
    line("NEUTRON ROUTE PLOTTER")
    rule()
    source_raw = input(GREEN + "\n  CURRENT SYSTEM > " + RESET)
    source = confirm_system(source_raw)
    dest_raw = input(GREEN + "  DESTINATION SYSTEM > " + RESET)
    dest = confirm_system(dest_raw)
    jump_range_raw = input(GREEN + "  JUMP RANGE (LY) > " + RESET)

    try:
        jump_range = float(jump_range_raw)
        result = run_with_spinner(
            "PLOTTING ROUTE",
            plot_neutron_route,
            source, dest, jump_range=jump_range
        )
        waypoints = result.get("waypoints", [])
        if not waypoints:
            print(BRIGHT + "\n  [NO ROUTE RETURNED]\n" + RESET)
            input(GREEN + "  PRESS ENTER TO RETURN..." + RESET)
            return

        print(BRIGHT + f"\n  ROUTE FOUND — {len(waypoints)} JUMPS\n" + RESET)
        for stop in waypoints[:10]:
            tag = "* NEUTRON" if stop["neutron_star"] else ""
            line(f"  {stop['system']} {tag}")
        input(GREEN + "\n  PRESS ENTER TO BEGIN ROUTE..." + RESET)

        save_route(source, dest, jump_range, waypoints, 0)
        run_jump_tracker(source, dest, jump_range, waypoints, 0)

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
    run_jump_tracker(
        saved["source"], saved["destination"], saved["jump_range"],
        saved["waypoints"], saved["current_index"]
    )

def standard_route():
    clear()
    border_top()
    line("STANDARD ROUTE PLOTTER")
    rule()
    dest = input(GREEN + "\n  DESTINATION SYSTEM > " + RESET)
    print(BRIGHT + f"\n  [FEATURE NOT YET IMPLEMENTED]\n" + RESET)
    input(GREEN + "  PRESS ENTER TO RETURN..." + RESET)

def system_info():
    clear()
    border_top()
    line("SYSTEM INFO")
    rule()
    print(BRIGHT + "\n  [JOURNAL LINK NOT YET IMPLEMENTED]\n" + RESET)
    input(GREEN + "  PRESS ENTER TO RETURN..." + RESET)

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
