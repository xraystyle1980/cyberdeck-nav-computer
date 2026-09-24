import sys
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
    print(BRIGHT + "| " + text.ljust(WIDTH - 4) + " |" + RESET)

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
    line("[1] NEUTRON ROUTE")
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
        route = plot_neutron_route(start, dest, jump_range=jump_range)
        print(BRIGHT + f"\n  ROUTE FOUND — {len(route)} JUMPS\n" + RESET)
        for stop in route[:10]:
            tag = "* NEUTRON" if stop["neutron_star"] else ""
            line(f"  {stop['system']} {tag}")
    except Exception as e:
        print(BRIGHT + f"\n  [ERROR: {e}]\n" + RESET)
    input(GREEN + "\n  PRESS ENTER TO RETURN..." + RESET)

def main():
    while True:
        draw_main_menu()
        choice = input(GREEN + "  > " + RESET).strip().lower()
        if choice == "1":
            neutron_route()
        elif choice == "q":
            clear()
            print(BRIGHT + "NAV COMPUTER OFFLINE.\n" + RESET)
            sys.exit(0)

if __name__ == "__main__":
    main()
