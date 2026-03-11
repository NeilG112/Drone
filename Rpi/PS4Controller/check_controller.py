#!/usr/bin/env python3
"""
DS4 / PS4 Controller Diagnostic Tool
--------------------------------------
Run this to verify your controller is detected and to check
the axis/button indices before using PS4_Rpi.py.

Usage:
  /home/neil/Code/DroneProject/FlightTesting/venv/bin/python3 check_controller.py

If no controller is found, first run:
  sudo modprobe hid_sony
Then reconnect the DS4 (press PS button), then re-run this script.
"""

import sys
import time
import pygame

EXPECTED_DS4 = {
    "axes":    6,   # LX, LY, L2, RX, RY, R2
    "buttons": 13,  # Cross(0), Circle(1), Square(2), Triangle(3),
                    # L1(4), R1(5), L2btn(6), R2btn(7),
                    # Share(8), Options(9), PS(10), L3(11), R3(12)
    "hats":    1,   # D-pad
}

AXIS_NAMES = {
    0: "Left X  (Yaw)",
    1: "Left Y  (Pitch)",
    2: "L2 Trigger",
    3: "Right X (Roll)",
    4: "Right Y",
    5: "R2 Trigger (Throttle)",
}

BUTTON_NAMES = {
    0:  "Cross    (X)   → Arm",
    1:  "Circle   (O)   → Kill",
    2:  "Square   (□)   → Connect",
    3:  "Triangle (△)",
    4:  "L1             → Yaw left",
    5:  "R1             → Yaw right",
    6:  "L2 (digital)",
    7:  "R2 (digital)",
    8:  "Share",
    9:  "Options",
    10: "PS Button",
    11: "L3 (stick click)",
    12: "R3 (stick click)",
}

def clear_line():
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

def main():
    pygame.init()
    pygame.joystick.init()

    print("=" * 60)
    print("  DS4 / PS4 Controller Diagnostic")
    print("=" * 60)

    count = pygame.joystick.get_count()
    if count == 0:
        print("\n  ❌  No joystick detected by pygame!\n")
        print("  Possible fix:")
        print("    1. Run:  sudo modprobe hid_sony")
        print("    2. Reconnect DS4 (press PS button)")
        print("    3. Re-run this script")
        print()
        pygame.quit()
        sys.exit(1)

    joy = pygame.joystick.Joystick(0)
    joy.init()
    name    = joy.get_name()
    n_axes  = joy.get_numaxes()
    n_btns  = joy.get_numbuttons()
    n_hats  = joy.get_numhats()

    print(f"\n  ✅  Controller detected: {name}")
    print(f"     Axes={n_axes}  Buttons={n_btns}  Hats={n_hats}")

    # Warn if counts differ from expected DS4
    ok = True
    if n_axes != EXPECTED_DS4["axes"]:
        print(f"  ⚠️  Expected {EXPECTED_DS4['axes']} axes, got {n_axes}")
        ok = False
    if n_btns != EXPECTED_DS4["buttons"]:
        print(f"  ⚠️  Expected {EXPECTED_DS4['buttons']} buttons, got {n_btns}")
        ok = False
    if ok:
        print("     Counts match expected DS4 layout ✓")

    print("\n  Move sticks / press buttons — Ctrl+C to quit\n")
    print("-" * 60)

    prev_btns = [False] * n_btns
    clock = pygame.time.Clock()

    try:
        while True:
            pygame.event.pump()

            # Print axes on one updating line
            axis_str = "  Axes: " + "  ".join(
                f"A{i}={joy.get_axis(i):+.2f}" for i in range(n_axes)
            )
            sys.stdout.write("\r" + axis_str.ljust(70))
            sys.stdout.flush()

            # Print button presses on new lines
            for b in range(n_btns):
                pressed = joy.get_button(b)
                if pressed and not prev_btns[b]:
                    label = BUTTON_NAMES.get(b, f"Button {b}")
                    print(f"\n  BTN {b:2d} pressed  → {label}")
                prev_btns[b] = pressed

            # D-pad
            for h in range(n_hats):
                hat = joy.get_hat(h)
                if hat != (0, 0):
                    print(f"\n  Hat {h}: {hat}")

            clock.tick(30)

    except KeyboardInterrupt:
        print("\n\n  Done.")

    pygame.quit()


if __name__ == "__main__":
    main()
