import shutil
import sys
import counter_link
import route_store
from spansh_client import lookup_system, plot_neutron_route

GREEN = "\033[32m"
BRIGHT = "\033[92m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

WIDTH = 64

def clear():
    print(CLEAR, end="")

def border():
    print(BRIGHT + "+" + "-" * (WIDTH - 2) + "+" + RESET)

def line(text=""):
    print(BRIGHT + "| " + text[:WIDTH - 4].ljust(WIDTH - 4) + " |" + RESET)

def blank():
    line("")

BANNER = [
    " N A V   C O M P U T E R",
    " -------------------------",
    " FSD NAVIGATION INTERFACE v0.1",
]

def draw_main_menu():
    clear()
    border()
    blank()
    for l in BANNER:
        line(l)
    blank()
    active = sum(r["status"] == "active" for r in route_store.load_all())
    line("[1] NEUTRON ROUTE")
    line(f"[2] SAVED ROUTES ({active} ACTIVE)")
    line("[Q] QUIT")
    blank()
    border()

# Remembered between plots so repeat routes only need a destination
last_start = "Sol"
last_range = 50.0

def ask_system(prompt, default=None):
    """Prompt until the name matches a known system; None if Spansh is unreachable."""
    hint = f" [{default}]" if default else ""
    while True:
        typed = input(GREEN + f"\n  {prompt}{hint} > " + RESET).strip() or default
        if not typed:
            continue
        try:
            exact, suggestions = lookup_system(typed)
        except Exception as e:
            print(BRIGHT + f"\n  [LOOKUP FAILED: {e}]" + RESET)
            return None
        if exact:
            print(BRIGHT + f"  LOCKED: {exact.upper()}" + RESET)
            return exact
        if not suggestions:
            print(BRIGHT + f"  [NO SYSTEM MATCHES '{typed.upper()}' — TRY AGAIN]" + RESET)
            continue
        print(BRIGHT + "  DID YOU MEAN:" + RESET)
        for i, name in enumerate(suggestions, 1):
            print(BRIGHT + f"    [{i}] {name}" + RESET)
        pick = input(GREEN + "  SELECT # OR ENTER TO RETYPE > " + RESET).strip()
        if pick.isdigit() and 1 <= int(pick) <= len(suggestions):
            name = suggestions[int(pick) - 1]
            print(BRIGHT + f"  LOCKED: {name.upper()}" + RESET)
            return name

def ask_jump_range(default):
    while True:
        typed = input(GREEN + f"\n  JUMP RANGE LY [{default:g}] > " + RESET).strip()
        if not typed:
            return default
        try:
            jump_range = float(typed)
        except ValueError:
            jump_range = 0
        if 1 <= jump_range <= 100:
            return jump_range
        print(BRIGHT + "  [ENTER A RANGE FROM 1 TO 100 LY]" + RESET)

def neutron_route():
    global last_start, last_range
    clear()
    border()
    line("NEUTRON ROUTE PLOTTER")
    border()
    start = ask_system("START SYSTEM", last_start)
    dest = start and ask_system("DESTINATION SYSTEM")
    if not dest:
        input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)
        return
    jump_range = ask_jump_range(last_range)
    last_start, last_range = start, jump_range
    print(BRIGHT + f"\n  [PLOTTING {start.upper()} -> {dest.upper()} @ {jump_range:g} LY...]" + RESET)
    try:
        plot = plot_neutron_route(start, dest, jump_range=jump_range)
    except Exception as e:
        print(BRIGHT + f"\n  [ERROR: {e}]\n" + RESET)
        input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)
        return
    default = route_store.default_name(plot)
    print(BRIGHT + f"\n  ROUTE FOUND — {len(plot['waypoints'])} WAYPOINTS" + RESET)
    route_name = input(GREEN + f"  ROUTE NAME [{default}] > " + RESET)
    route = route_store.create(plot, route_name)
    route_view(route, "ROUTE PLOTTED AND SAVED")

def route_view(route, message=None):
    """Show a route and track progress; the counter shows jumps remaining meanwhile."""
    try:
        _route_view(route, message)
    finally:
        counter_link.clear()

def _route_view(route, message):
    while True:
        counter_link.show_jumps(route_store.jumps_remaining(route))
        waypoints = route["waypoints"]
        pos, last = route["position"], len(waypoints) - 1
        done = route["status"] == "completed"
        clear()
        border()
        line(route_store.name(route).upper())
        if route_store.name(route) != route_store.default_name(route):
            line(route_store.default_name(route).upper())
        line(f"{route['distance']:,.0f} LY | {len(waypoints)} WAYPOINTS | "
             f"{route_store.total_jumps(route)} JUMPS | {route['range']:g} LY RANGE")
        if done:
            line(f"ROUTE COMPLETE {route['completed']}")
        else:
            line(f"AT WAYPOINT {pos}/{last} | {route_store.jumps_remaining(route)} JUMPS, "
                 f"{waypoints[pos]['distance_left']:,.0f} LY TO GO")
        border()
        rows = max(5, shutil.get_terminal_size().lines - 14)
        first = max(0, min(pos - 2, len(waypoints) - rows))
        for i in range(first, min(first + rows, len(waypoints))):
            w = waypoints[i]
            mark = ">" if i == pos else ("-" if i < pos else " ")
            tag = "NEUTRON" if w["neutron_star"] else ""
            line(f"{mark} {i:>3}  {w['system'][:30]:<30} {w['jumps']:>3} J  {tag}")
        border()
        if message:
            print(BRIGHT + f"  {message}" + RESET)
            message = None
        toggle = "[R] REOPEN" if done else "[C] COMPLETE"
        print(GREEN + "  [N] NEXT  [P] PREV  [#] GO TO WAYPOINT" + RESET)
        print(GREEN + f"  {toggle}  [E] NAME  [D] DELETE  [ENTER] BACK" + RESET)
        choice = input(GREEN + "  > " + RESET).strip().lower()

        if choice in ("", "b"):
            return
        if choice in ("n", "p") or choice.isdigit():
            target = pos + 1 if choice == "n" else pos - 1 if choice == "p" else int(choice)
            if done and target >= last:
                continue
            if done:
                route_store.reopen(route)
            route_store.set_position(route, target)
            if route["status"] == "completed" and not done:
                message = "DESTINATION REACHED — ROUTE COMPLETE"
        elif choice == "c" and not done:
            route_store.mark_complete(route)
            message = "ROUTE MARKED COMPLETE"
        elif choice == "r" and done:
            route_store.reopen(route)
            message = "ROUTE REOPENED"
        elif choice == "e":
            new_name = input(GREEN + f"  NEW NAME [{route_store.name(route)}] > " + RESET)
            if new_name.strip():
                route_store.rename(route, new_name)
                message = "ROUTE RENAMED"
        elif choice == "d":
            if input(GREEN + "  DELETE THIS ROUTE? Y/N > " + RESET).strip().lower() == "y":
                route_store.delete(route)
                return

def saved_routes():
    while True:
        routes = route_store.load_all()
        clear()
        border()
        line("SAVED ROUTES")
        border()
        if not routes:
            line("NO SAVED ROUTES — PLOT ONE FROM THE MAIN MENU")
            border()
            input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)
            return
        rows = max(5, shutil.get_terminal_size().lines - 8)
        for i, r in enumerate(routes[:rows], 1):
            progress = "DONE" if r["status"] == "completed" else f"{r['position']}/{len(r['waypoints']) - 1}"
            line(f"[{i:>2}] {route_store.name(r)[:32]:<32} {progress:>7} {r['created'][:10]}")
        if len(routes) > rows:
            line(f"(+{len(routes) - rows} OLDER NOT SHOWN)")
        border()
        pick = input(GREEN + "  SELECT # OR ENTER TO RETURN > " + RESET).strip()
        if not pick:
            return
        if pick.isdigit() and 1 <= int(pick) <= min(len(routes), rows):
            route_view(routes[int(pick) - 1])

def main():
    while True:
        draw_main_menu()
        choice = input(GREEN + "  > " + RESET).strip().lower()
        if choice == "1":
            neutron_route()
        elif choice == "2":
            saved_routes()
        elif choice == "q":
            clear()
            print(BRIGHT + "NAV COMPUTER OFFLINE.\n" + RESET)
            sys.exit(0)

if __name__ == "__main__":
    main()
