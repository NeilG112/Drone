#!/usr/bin/env python3
"""
PS4 / DualShock 4 Controller Mapping
======================================
Live display of every axis, button, and hat for the PS4 controller
connected via Bluetooth.  Use this to verify the controller layout
before running the main PS4_Rpi.py drone control script.

Standard SDL2 axis / button layout on Linux (Bluetooth DS4):
─────────────────────────────────────────────────────────────
AXES
  0  Left Stick X    (-1 = left,    +1 = right)
  1  Left Stick Y    (-1 = up,      +1 = down)
  2  L2 Trigger      (-1 = released, +1 = fully pressed)
  3  Right Stick X   (-1 = left,    +1 = right)
  4  Right Stick Y   (-1 = up,      +1 = down)
  5  R2 Trigger      (-1 = released, +1 = fully pressed)

BUTTONS
  0  Cross    (X)
  1  Circle   (O)
  2  Square   (□)
  3  Triangle (△)
  4  L1
  5  R1
  6  L2  (digital)
  7  R2  (digital)
  8  Share
  9  Options
 10  PS Button
 11  L3  (Left Stick Click)
 12  R3  (Right Stick Click)

HAT (D-Pad)
  Hat 0: (x, y) where x/y ∈ {-1, 0, +1}
  (-1, 0)=Left  (1,0)=Right  (0,1)=Up  (0,-1)=Down

Usage:
  /home/neil/Code/DroneProject/FlightTesting/venv/bin/python3 ControllerMapping.py
"""

import sys
import time
import pygame

# ─── Controller Layout ────────────────────────────────────────────────────────

AXIS_MAP = {
    0: ("Left Stick X",  "Yaw / Steer left-right"),
    1: ("Left Stick Y",  "Pitch / Forward-back  "),
    2: ("L2 Trigger  ",  "Analogue L2           "),
    3: ("Right Stick X", "Roll / Steer left-right"),
    4: ("Right Stick Y", "Unused / Elevation    "),
    5: ("R2 Trigger  ",  "Throttle              "),
}

BUTTON_MAP = {
    0:  ("Cross    ✕", "Arm / Confirm"),
    1:  ("Circle   O", "Kill / Cancel"),
    2:  ("Square   □", "Connect / Option A"),
    3:  ("Triangle △", "Option B"),
    4:  ("L1",         "Yaw bump left"),
    5:  ("R1",         "Yaw bump right"),
    6:  ("L2 (btn)",   "Throttle-cut digital"),
    7:  ("R2 (btn)",   "Throttle digital"),
    8:  ("Share",      ""),
    9:  ("Options",    ""),
    10: ("PS Button",  ""),
    11: ("L3",         "Left stick click"),
    12: ("R3",         "Right stick click"),
}

TRIGGER_AXES = {2, 5}   # triggers rest at -1, travel to +1
DEADZONE = 0.04


# ─── Helpers ──────────────────────────────────────────────────────────────────

def bar(value: float, width: int = 20, bilateral: bool = True) -> str:
    """Return a text progress bar for a normalised value."""
    if bilateral:
        # value in [-1, +1]
        mid = width // 2
        norm = max(-1.0, min(1.0, value))
        filled = int(abs(norm) * mid)
        if norm >= 0:
            return "[" + " " * mid + "█" * filled + " " * (mid - filled) + "]"
        else:
            return "[" + " " * (mid - filled) + "█" * filled + " " * mid + "]"
    else:
        # value in [0, 1]
        norm = max(0.0, min(1.0, value))
        filled = int(norm * width)
        return "[" + "█" * filled + " " * (width - filled) + "]"


def trigger_normalise(raw: float) -> float:
    """Convert trigger axis from [-1, +1] to [0, 1]."""
    return (raw + 1.0) / 2.0


def apply_deadzone(v: float) -> float:
    if abs(v) < DEADZONE:
        return 0.0
    sign = 1 if v > 0 else -1
    return sign * (abs(v) - DEADZONE) / (1.0 - DEADZONE)


def hat_direction(h: tuple) -> str:
    x, y = h
    dirs = []
    if y > 0:  dirs.append("UP")
    if y < 0:  dirs.append("DOWN")
    if x < 0:  dirs.append("LEFT")
    if x > 0:  dirs.append("RIGHT")
    return "+".join(dirs) if dirs else "CENTRE"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    pygame.joystick.init()

    print()
    print("=" * 68)
    print("  PS4 / DualShock 4  —  Controller Mapping")
    print("=" * 68)

    # ── Wait for controller ──────────────────────────────────────────────
    attempts = 0
    joy = None
    while joy is None:
        pygame.joystick.quit()
        pygame.joystick.init()
        count = pygame.joystick.get_count()

        if count > 0:
            joy = pygame.joystick.Joystick(0)
            joy.init()
        else:
            if attempts == 0:
                print("\n  ⏳  No controller detected — waiting for PS4 controller…")
                print("      Make sure Bluetooth is on and press the PS button.\n")
            attempts += 1
            time.sleep(1.0)
            pygame.event.pump()

    # ── Print controller summary ─────────────────────────────────────────
    name    = joy.get_name()
    n_axes   = joy.get_numaxes()
    n_btns   = joy.get_numbuttons()
    n_hats   = joy.get_numhats()

    print(f"\n  ✅  Controller  : {name}")
    print(f"      Axes       : {n_axes}")
    print(f"      Buttons    : {n_btns}")
    print(f"      Hats       : {n_hats}")

    # Warn if the counts differ from the expected DS4 values
    EXPECTED = {"axes": 6, "buttons": 13, "hats": 1}
    layout_ok = True
    if n_axes != EXPECTED["axes"]:
        print(f"\n  ⚠️  Expected {EXPECTED['axes']} axes, got {n_axes}")
        layout_ok = False
    if n_btns != EXPECTED["buttons"]:
        print(f"  ⚠️  Expected {EXPECTED['buttons']} buttons, got {n_btns}")
        layout_ok = False
    if n_hats != EXPECTED["hats"]:
        print(f"  ⚠️  Expected {EXPECTED['hats']} hat, got {n_hats}")
        layout_ok = False
    if layout_ok:
        print("      Layout     : matches standard DS4  ✓")

    print()
    print("  Move sticks, press buttons — Ctrl+C to quit")
    print("-" * 68)
    print()

    # ── Live display ─────────────────────────────────────────────────────
    prev_buttons = [False] * n_btns
    prev_hats    = [(0, 0)] * n_hats
    clock = pygame.time.Clock()

    HEADER_INTERVAL = 20   # reprint axis header every N frames
    frame = 0

    def print_axis_header():
        sys.stdout.write(
            "\n  {:<16} {:<10} {:<23} {}\n".format(
                "AXIS NAME", "RAW", "BAR", "FUNCTION"
            )
        )
        sys.stdout.write("  " + "-" * 64 + "\n")

    try:
        while True:
            pygame.event.pump()
            frame += 1

            if frame % HEADER_INTERVAL == 1:
                print_axis_header()

            # ── Axes ────────────────────────────────────────────────────
            axis_lines = []
            for i in range(n_axes):
                raw = joy.get_axis(i)
                name_str, func = AXIS_MAP.get(i, (f"Axis {i}", ""))

                if i in TRIGGER_AXES:
                    norm = trigger_normalise(raw)
                    b = bar(norm, width=20, bilateral=False)
                    axis_lines.append(
                        f"  A{i} {name_str:<16} {raw:+.3f}  {b}  {func}"
                    )
                else:
                    dz = apply_deadzone(raw)
                    b = bar(dz, width=20, bilateral=True)
                    axis_lines.append(
                        f"  A{i} {name_str:<16} {raw:+.3f}  {b}  {func}"
                    )

            # Print axes block (overwrite in place using ANSI up-cursor)
            lines_to_overwrite = len(axis_lines) + 1   # +1 for blank separation
            sys.stdout.write(f"\033[{lines_to_overwrite}A")
            sys.stdout.write("\033[J")                 # erase to end of screen
            for line in axis_lines:
                sys.stdout.write(line + "\n")
            sys.stdout.write("\n")
            sys.stdout.flush()

            # ── Buttons (print on press/release) ────────────────────────
            for b_idx in range(n_btns):
                pressed = bool(joy.get_button(b_idx))
                if pressed != prev_buttons[b_idx]:
                    label, func = BUTTON_MAP.get(b_idx, (f"Btn {b_idx}", ""))
                    state = "PRESSED " if pressed else "released"
                    ts    = time.strftime("%H:%M:%S")
                    extra = f"  ← {func}" if func else ""
                    print(f"  [{ts}]  BTN {b_idx:2d}  {state:<8}  {label}{extra}")
                prev_buttons[b_idx] = pressed

            # ── Hat / D-pad ─────────────────────────────────────────────
            for h_idx in range(n_hats):
                h = joy.get_hat(h_idx)
                if h != prev_hats[h_idx]:
                    ts = time.strftime("%H:%M:%S")
                    direction = hat_direction(h)
                    print(f"  [{ts}]  HAT {h_idx}  {direction}")
                prev_hats[h_idx] = h

            clock.tick(20)   # 20 Hz refresh

    except KeyboardInterrupt:
        pass

    print("\n\n  Exiting — controller mapping complete.\n")
    pygame.quit()


if __name__ == "__main__":
    main()
