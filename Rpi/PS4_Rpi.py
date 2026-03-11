#!/usr/bin/env python3
"""
PS4 Controller → Drone (Betaflight via MAVLink)
Uses pygame for controller input and real-time UI rendering.

Controls:
  R2          → Throttle (proportional 1000–2000)
  Left Stick  → Yaw (X) / Pitch (Y)
  Right Stick → Roll (X)
  L1 / R1     → Yaw bump left / right
  X (Cross)   → Arm
  □ (Square)  → Connect to FC
  O (Circle)  → KILL SWITCH (force disarm)
"""

import sys
import time
import math
import threading
from collections import deque

import pygame
from pymavlink import mavutil

# ─── Configuration ────────────────────────────────────────────────────────────
# Connect via UDP (Raspberry Pi forwards MAVLink over network)
MAVLINK_CONNECTION = "udpin:0.0.0.0:14550"

RC_MIN = 1000
RC_MAX = 2000
RC_MID = 1500

DEADZONE = 0.08          # joystick dead zone
YAW_BUMP_VALUE = 300     # L1/R1 yaw offset from center
SEND_RATE_HZ = 20        # MAVLink send rate
UI_FPS = 30              # UI render rate

# ─── PS4 button indices (pygame, Linux / SDL2) ──────────────────────────────
BTN_CROSS = 0             # X  → Arm
BTN_CIRCLE = 1            # O  → Kill
BTN_SQUARE = 2            # □  → Connect
BTN_TRIANGLE = 3          # △
BTN_L1 = 4                # L1 → Yaw left
BTN_R1 = 5                # R1 → Yaw right
BTN_L2 = 6
BTN_R2 = 7
BTN_SHARE = 8
BTN_OPTIONS = 9
BTN_PS = 10
BTN_L3 = 11
BTN_R3 = 12

# Axis indices (SDL2 DS4 mapping on Linux)
AXIS_LEFT_X = 0           # Yaw
AXIS_LEFT_Y = 1           # Pitch
AXIS_L2 = 2               # L2 trigger
AXIS_RIGHT_X = 3          # Roll
AXIS_RIGHT_Y = 4          # (unused)
AXIS_R2 = 5               # R2 trigger → Throttle

# ─── Colors ──────────────────────────────────────────────────────────────────
BG_COLOR       = (18, 18, 24)
PANEL_BG       = (28, 28, 38)
PANEL_BORDER   = (50, 50, 65)
TEXT_DIM       = (120, 120, 140)
TEXT_NORMAL    = (200, 200, 215)
TEXT_BRIGHT    = (240, 240, 255)
ACCENT_BLUE    = (70, 130, 255)
ACCENT_GREEN   = (50, 205, 120)
ACCENT_RED     = (255, 60, 80)
ACCENT_ORANGE  = (255, 165, 50)
ACCENT_PURPLE  = (150, 100, 255)
ACCENT_CYAN    = (0, 210, 230)
ACCENT_YELLOW  = (255, 220, 60)
BAR_BG         = (40, 40, 55)
KILL_FLASH     = (200, 30, 40)
THROTTLE_LOW   = (50, 205, 120)
THROTTLE_HIGH  = (255, 60, 80)
BTN_HOVER      = (55, 55, 75)

# ─── Window ──────────────────────────────────────────────────────────────────
WIN_W, WIN_H = 960, 720


class DroneController:
    """Main application: PS4 input → MAVLink RC → pygame UI."""

    def __init__(self):
        # RC channel values (1000–2000)
        self.throttle = RC_MIN
        self.roll = RC_MID
        self.pitch = RC_MID
        self.yaw = RC_MID

        # State
        self.running = True
        self.armed = False
        self.killed = False
        self.connected = False
        self.connecting = False
        self.controller_connected = False
        self.controller_name = ""
        self.master = None
        self.joystick = None

        # MAVLink timing
        self.last_heartbeat_time = 0
        self.last_fc_msg = ""

        # Raw input values for UI display (-1..1 or 0..1)
        self.raw_throttle = 0.0
        self.raw_roll = 0.0
        self.raw_pitch = 0.0
        self.raw_yaw = 0.0
        self.l1_pressed = False
        self.r1_pressed = False

        # Logs
        self.logs = deque(maxlen=14)


        # Kill flash animation
        self.kill_flash_time = 0

        # UI button rects (set during draw)
        self.btn_kill_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_disarm_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_arm_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_connect_rect = pygame.Rect(0, 0, 0, 0)

    # ─── Logging ─────────────────────────────────────────────────────────
    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")

    # ─── Controller ──────────────────────────────────────────────────────
    def init_controller(self):
        """Try to find and initialize a PS4 / DS4 controller."""
        pygame.joystick.quit()
        pygame.joystick.init()
        count = pygame.joystick.get_count()

        if count > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.controller_name = self.joystick.get_name()
            self.controller_connected = True

            # One-time diagnostic — shows axis/button layout at init
            n_axes   = self.joystick.get_numaxes()
            n_btns   = self.joystick.get_numbuttons()
            n_hats   = self.joystick.get_numhats()
            self.log(f"Controller: {self.controller_name}")
            self.log(f"  Axes={n_axes}  Buttons={n_btns}  Hats={n_hats}")
            return True
        else:
            self.controller_connected = False
            self.joystick = None
            return False

    def apply_deadzone(self, value):
        if abs(value) < DEADZONE:
            return 0.0
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - DEADZONE) / (1.0 - DEADZONE)

    def process_input(self):
        """Read PS4 controller and update RC values."""
        if not self.joystick or not self.controller_connected:
            return

        try:
            num_axes = self.joystick.get_numaxes()
            num_buttons = self.joystick.get_numbuttons()
        except pygame.error:
            self.controller_connected = False
            self.throttle = RC_MIN
            return

        # ── R2 trigger → Throttle ──
        if num_axes > AXIS_R2:
            r2_raw = self.joystick.get_axis(AXIS_R2)
            self.raw_throttle = (r2_raw + 1.0) / 2.0
            self.throttle = int(RC_MIN + self.raw_throttle * (RC_MAX - RC_MIN))
        else:
            if num_buttons > BTN_R2 and self.joystick.get_button(BTN_R2):
                self.throttle = RC_MAX
                self.raw_throttle = 1.0
            else:
                self.throttle = RC_MIN
                self.raw_throttle = 0.0

        # ── Right Stick X → Roll ──
        if num_axes > AXIS_RIGHT_X:
            rx = self.apply_deadzone(self.joystick.get_axis(AXIS_RIGHT_X))
            self.raw_roll = rx
            self.roll = int(RC_MID + rx * 500)

        # ── Left Stick Y → Pitch ──
        if num_axes > AXIS_LEFT_Y:
            ly = self.apply_deadzone(-self.joystick.get_axis(AXIS_LEFT_Y))
            self.raw_pitch = ly
            self.pitch = int(RC_MID + ly * 500)

        # ── Left Stick X → Yaw (proportional) ──
        if num_axes > AXIS_LEFT_X:
            lx = self.apply_deadzone(self.joystick.get_axis(AXIS_LEFT_X))
            self.raw_yaw = lx
            self.yaw = int(RC_MID + lx * 500)

        # ── L1 / R1 → Yaw bumps (override stick) ──
        self.l1_pressed = num_buttons > BTN_L1 and self.joystick.get_button(BTN_L1)
        self.r1_pressed = num_buttons > BTN_R1 and self.joystick.get_button(BTN_R1)

        if self.l1_pressed and not self.r1_pressed:
            self.yaw = RC_MID - YAW_BUMP_VALUE
            self.raw_yaw = -YAW_BUMP_VALUE / 500.0
        elif self.r1_pressed and not self.l1_pressed:
            self.yaw = RC_MID + YAW_BUMP_VALUE
            self.raw_yaw = YAW_BUMP_VALUE / 500.0

        # Clamp
        self.throttle = max(RC_MIN, min(RC_MAX, self.throttle))
        self.roll = max(RC_MIN, min(RC_MAX, self.roll))
        self.pitch = max(RC_MIN, min(RC_MAX, self.pitch))
        self.yaw = max(RC_MIN, min(RC_MAX, self.yaw))

    # ─── MAVLink ─────────────────────────────────────────────────────────
    def mavlink_connect(self):
        """Connect to flight controller in a background thread."""
        if self.connected or self.connecting:
            self.log("Already connected or connecting...")
            return
        
        # Reset state on new connection attempt (allows recovery after kill)
        self.killed = False
        self.throttle = RC_MIN
        self.raw_throttle = 0.0
        
        self.connecting = True
        try:
            self.log(f"Connecting to {MAVLINK_CONNECTION}...")
            self.master = mavutil.mavlink_connection(MAVLINK_CONNECTION)
            self.log("Waiting for FC heartbeat...")
            self.master.wait_heartbeat()
            self.connected = True
            self.log(f"FC connected (sys={self.master.target_system} comp={self.master.target_component})")
            self.last_heartbeat_time = time.time()
        except Exception as e:
            self.log(f"Connection failed: {e}")
            self.connected = False
        finally:
            self.connecting = False

    def send_gcs_heartbeat(self):
        """Send GCS heartbeat to keep the connection alive (must be called at ~1 Hz)."""
        if self.master and self.connected:
            try:
                self.master.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, 0
                )
            except Exception:
                pass

    def mavlink_recv_loop(self):
        """Read FC messages and update state based on responses."""
        while self.running:
            if not self.master or not self.connected:
                time.sleep(0.1)
                continue

            # Send GCS heartbeat at 1 Hz
            now = time.time()
            if now - self.last_heartbeat_time > 1.0:
                self.send_gcs_heartbeat()
                self.last_heartbeat_time = now

            # Read messages
            try:
                msg = self.master.recv_match(blocking=False)
            except Exception:
                time.sleep(0.01)
                continue

            if not msg:
                time.sleep(0.01)
                continue

            msg_type = msg.get_type()

            if msg_type == "STATUSTEXT":
                text = msg.text
                self.log(f"[FC] {text}")

            elif msg_type == "COMMAND_ACK":
                cmd = msg.command
                result = msg.result
                result_str = {
                    0: "ACCEPTED", 1: "TEMPORARILY_REJECTED",
                    2: "DENIED", 3: "UNSUPPORTED",
                    4: "FAILED", 5: "IN_PROGRESS", 6: "CANCELLED"
                }.get(result, f"UNKNOWN({result})")
                if cmd == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                    self.log(f"[CMD] ARM/DISARM: {result_str}")
                else:
                    self.log(f"[CMD] {cmd}: {result_str}")

            elif msg_type == "HEARTBEAT":
                is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if is_armed != self.armed:
                    self.armed = is_armed
                    status = "ARMED" if self.armed else "DISARMED"
                    self.log(f"[FC] Vehicle is now {status}")
                    if not self.armed:
                        self.killed = False

            time.sleep(0.01)

    def mavlink_send_loop(self):
        """Send RC override at fixed rate."""
        while self.running:
            if self.master and self.connected and not self.killed:
                try:
                    self.master.mav.rc_channels_override_send(
                        self.master.target_system,
                        self.master.target_component,
                        self.roll,      # ch1: Roll
                        self.pitch,     # ch2: Pitch
                        self.throttle,  # ch3: Throttle
                        self.yaw,       # ch4: Yaw
                        0, 0, 0, 0     # ch5-8: no override
                    )
                except Exception as e:
                    self.log(f"Send error: {e}")
            time.sleep(1.0 / SEND_RATE_HZ)

    def arm_drone(self):
        if not self.master or not self.connected:
            self.log("Cannot arm: not connected")
            return
        if self.armed:
            self.log("Already armed")
            return
        try:
            self.log("Sending ARM command...")
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1,   # param1 = 1 → arm
                0, 0, 0, 0, 0, 0
            )
            # State update handled by mavlink_recv_loop (HEARTBEAT)
        except Exception as e:
            self.log(f"Arm failed: {e}")

    def disarm_drone(self):
        """Normal disarm (only works when not in flight)."""
        if not self.master or not self.connected:
            self.log("Cannot disarm: not connected")
            return
        if not self.armed:
            self.log("Already disarmed")
            return
        try:
            self.log("Sending DISARM command...")
            self.throttle = RC_MIN
            self.raw_throttle = 0.0
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                0,   # param1 = 0 → disarm
                0, 0, 0, 0, 0, 0
            )
            # State update handled by mavlink_recv_loop (HEARTBEAT)
        except Exception as e:
            self.log(f"Disarm failed: {e}")

    def kill_motors(self):
        """Emergency kill: force disarm regardless of flight state."""
        if self.killed:
            return

        self.log("!!! KILL SWITCH ACTIVATED !!!")
        self.throttle = RC_MIN
        self.raw_throttle = 0.0
        self.killed = True
        self.armed = False
        self.kill_flash_time = time.time()

        if self.master and self.connected:
            try:
                # Zero throttle immediately
                self.master.mav.rc_channels_override_send(
                    self.master.target_system,
                    self.master.target_component,
                    0, 0, RC_MIN, 0,
                    0, 0, 0, 0
                )
                # Force disarm: param2 = 21196 bypasses all safety checks
                self.master.mav.command_long_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,
                    0,       # param1 = 0 → disarm
                    21196,   # param2 = 21196 → FORCE (magic number)
                    0, 0, 0, 0, 0
                )
                self.log("FORCE DISARM SENT")
            except Exception as e:
                self.log(f"Kill error: {e}")

    def shutdown(self):
        """Clean shutdown."""
        self.kill_motors()
        self.running = False
        if self.master:
            try:
                self.master.mav.command_long_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,
                    0, 21196, 0, 0, 0, 0, 0
                )
            except Exception:
                pass
        self.log("Shutdown complete")

    # ─── UI Rendering ────────────────────────────────────────────────────
    def draw_ui(self, screen, fonts):
        """Draw the entire UI."""
        screen.fill(BG_COLOR)
        font_sm, font_md, font_lg, font_xl, font_icon = fonts

        # Kill flash overlay
        if self.killed:
            elapsed = time.time() - self.kill_flash_time
            if elapsed < 3.0:
                alpha = int(40 * max(0, math.sin(elapsed * 6)))
                flash = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                flash.fill((*KILL_FLASH, alpha))
                screen.blit(flash, (0, 0))

        # ─── Header Bar ─────────────────────────────────────────────
        pygame.draw.rect(screen, PANEL_BG, (0, 0, WIN_W, 56))
        pygame.draw.line(screen, PANEL_BORDER, (0, 56), (WIN_W, 56))

        title = font_lg.render("DRONE CONTROLLER", True, TEXT_BRIGHT)
        screen.blit(title, (20, 14))

        # Status badges
        badge_x = WIN_W - 20
        badges = []
        if self.killed:
            badges.append(("KILLED", ACCENT_RED))
        elif self.armed:
            badges.append(("ARMED", ACCENT_GREEN))
        else:
            badges.append(("DISARMED", TEXT_DIM))

        if self.connecting:
            badges.append(("CONNECTING...", ACCENT_YELLOW))
        elif self.connected:
            badges.append(("FC CONNECTED", ACCENT_BLUE))
        else:
            badges.append(("FC OFFLINE", ACCENT_ORANGE))

        if self.controller_connected:
            badges.append(("CONTROLLER OK", ACCENT_GREEN))
        else:
            badges.append(("NO CONTROLLER", ACCENT_RED))

        for label, color in reversed(badges):
            tw = font_sm.size(label)[0]
            bw = tw + 16
            badge_x -= bw + 8
            pygame.draw.rect(screen, (*color, 30) if len(color) == 3 else color,
                             (badge_x, 16, bw, 24), border_radius=12)
            pygame.draw.rect(screen, color, (badge_x, 16, bw, 24), 1, border_radius=12)
            txt = font_sm.render(label, True, color)
            screen.blit(txt, (badge_x + 8, 20))

        y_start = 72

        # ─── Left Column: Channel Bars ──────────────────────────────
        col_left_x = 20
        col_w = 420

        self._draw_panel(screen, col_left_x, y_start, col_w, 280, "RC CHANNELS", fonts)

        channels = [
            ("THROTTLE", self.throttle, self.raw_throttle, ACCENT_RED, True),
            ("ROLL",     self.roll,     self.raw_roll,     ACCENT_BLUE, False),
            ("PITCH",    self.pitch,    self.raw_pitch,    ACCENT_GREEN, False),
            ("YAW",      self.yaw,      self.raw_yaw,     ACCENT_PURPLE, False),
        ]

        bar_y = y_start + 40
        for name, value, raw, color, is_throttle in channels:
            self._draw_channel_bar(screen, col_left_x + 16, bar_y, col_w - 32,
                                   name, value, raw, color, is_throttle, fonts)
            bar_y += 58

        # ─── Right Column: Stick Visualizer ──────────────────────────
        col_right_x = 460
        col_right_w = WIN_W - col_right_x - 20

        self._draw_panel(screen, col_right_x, y_start, col_right_w, 280,
                         "STICK INPUT", fonts)

        stick_size = 80
        lsx = col_right_x + col_right_w // 4
        lsy = y_start + 155
        self._draw_stick_viz(screen, lsx, lsy, stick_size,
                             self.raw_yaw, -self.raw_pitch,
                             "L STICK  (Yaw / Pitch)", ACCENT_PURPLE, fonts)

        rsx = col_right_x + 3 * col_right_w // 4
        rsy = y_start + 155
        self._draw_stick_viz(screen, rsx, rsy, stick_size,
                             self.raw_roll, 0,
                             "R STICK  (Roll)", ACCENT_BLUE, fonts)

        # ─── Middle Row: Action Buttons + Button Map ─────────────────
        action_y = y_start + 296
        action_h = 120

        # Action Buttons Panel
        btn_panel_w = 420
        self._draw_panel(screen, 20, action_y, btn_panel_w, action_h, "ACTIONS", fonts)

        btn_w = 90
        btn_h = 42
        btn_y = action_y + 40
        btn_gap = 12
        bx = 36

        # Connect button
        connect_color = ACCENT_BLUE if not self.connected else TEXT_DIM
        connect_label = "CONNECT" if not self.connected else "CONNECTED"
        self.btn_connect_rect = self._draw_ui_button(
            screen, bx, btn_y, btn_w, btn_h, connect_label,
            connect_color, not self.connected and not self.connecting, fonts)
        # PS4 hint
        hint_txt = font_sm.render("□", True, TEXT_DIM)
        screen.blit(hint_txt, (bx + btn_w // 2 - hint_txt.get_width() // 2, btn_y + btn_h + 4))
        bx += btn_w + btn_gap

        # Arm button
        arm_color = ACCENT_GREEN if not self.armed else TEXT_DIM
        arm_label = "ARM" if not self.armed else "ARMED"
        can_arm = self.connected and not self.armed and not self.killed
        self.btn_arm_rect = self._draw_ui_button(
            screen, bx, btn_y, btn_w, btn_h, arm_label,
            arm_color, can_arm, fonts)
        hint_txt = font_sm.render("✕", True, TEXT_DIM)
        screen.blit(hint_txt, (bx + btn_w // 2 - hint_txt.get_width() // 2, btn_y + btn_h + 4))
        bx += btn_w + btn_gap

        # Disarm button
        can_disarm = self.armed and not self.killed
        self.btn_disarm_rect = self._draw_ui_button(
            screen, bx, btn_y, btn_w, btn_h, "DISARM",
            ACCENT_ORANGE, can_disarm, fonts)
        bx += btn_w + btn_gap

        # Kill button
        self.btn_kill_rect = self._draw_ui_button(
            screen, bx, btn_y, btn_w, btn_h, "KILL",
            ACCENT_RED, not self.killed, fonts)
        hint_txt = font_sm.render("O", True, TEXT_DIM)
        screen.blit(hint_txt, (bx + btn_w // 2 - hint_txt.get_width() // 2, btn_y + btn_h + 4))

        # ─── Button Mapping Panel ────────────────────────────────────
        map_x = 460
        map_w = WIN_W - map_x - 20
        self._draw_panel(screen, map_x, action_y, map_w, action_h, "CONTROLLER MAP", fonts)

        mappings = [
            ("R2",       "Throttle",    ACCENT_RED),
            ("L-Stick",  "Yaw / Pitch", ACCENT_PURPLE),
            ("R-Stick",  "Roll",        ACCENT_BLUE),
            ("L1 / R1",  "Yaw Bump",    ACCENT_CYAN),
            ("✕ (X)",    "Arm",         ACCENT_GREEN),
            ("□ (Sq)",   "Connect",     ACCENT_BLUE),
            ("O (Cir)",  "KILL",        ACCENT_RED),
        ]

        mx = map_x + 16
        my = action_y + 36
        col2_offset = map_w // 2
        for i, (btn_label, action, color) in enumerate(mappings):
            col = 0 if i < 4 else 1
            row = i if i < 4 else i - 4
            cx = mx + col * col2_offset
            cy = my + row * 19
            bl = font_sm.render(btn_label, True, color)
            screen.blit(bl, (cx, cy))
            al = font_sm.render(f"→ {action}", True, TEXT_DIM)
            screen.blit(al, (cx + 68, cy))

        # ─── Bottom: Logs Panel ──────────────────────────────────────
        log_y = action_y + action_h + 16
        log_h = WIN_H - log_y - 16
        self._draw_panel(screen, 20, log_y, WIN_W - 40, log_h, "EVENT LOG", fonts)

        ly = log_y + 34
        for msg in list(self.logs):
            if ly + 16 > log_y + log_h - 8:
                break
            color = TEXT_DIM
            if "KILL" in msg or "FORCE" in msg:
                color = ACCENT_RED
            elif "ARMED" in msg or "✓" in msg:
                color = ACCENT_GREEN
            elif "Error" in msg or "failed" in msg or "disconnect" in msg:
                color = ACCENT_ORANGE
            elif "Connect" in msg or "connect" in msg:
                color = ACCENT_CYAN
            elif "DISARM" in msg:
                color = ACCENT_ORANGE

            txt = font_sm.render(msg, True, color)
            screen.blit(txt, (36, ly))
            ly += 18

    def _draw_panel(self, screen, x, y, w, h, title, fonts):
        """Draw a rounded panel with title."""
        font_sm = fonts[0]
        pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=8)
        pygame.draw.rect(screen, PANEL_BORDER, (x, y, w, h), 1, border_radius=8)
        ttl = font_sm.render(title, True, TEXT_DIM)
        screen.blit(ttl, (x + 16, y + 12))

    def _draw_ui_button(self, screen, x, y, w, h, label, color, enabled, fonts):
        """Draw a clickable UI button. Returns its rect."""
        font_md = fonts[1]
        rect = pygame.Rect(x, y, w, h)

        if enabled:
            # Check hover
            mouse_pos = pygame.mouse.get_pos()
            hovering = rect.collidepoint(mouse_pos)
            bg = BTN_HOVER if hovering else PANEL_BG
            pygame.draw.rect(screen, bg, rect, border_radius=6)
            pygame.draw.rect(screen, color, rect, 2, border_radius=6)
            txt = font_md.render(label, True, color)
        else:
            pygame.draw.rect(screen, PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(screen, PANEL_BORDER, rect, 1, border_radius=6)
            txt = font_md.render(label, True, TEXT_DIM)

        screen.blit(txt, (x + (w - txt.get_width()) // 2,
                          y + (h - txt.get_height()) // 2))
        return rect

    def _draw_channel_bar(self, screen, x, y, w, name, value, raw, color,
                          is_throttle, fonts):
        """Draw a labeled bar for an RC channel."""
        font_sm, font_md = fonts[0], fonts[1]

        lbl = font_sm.render(name, True, TEXT_NORMAL)
        screen.blit(lbl, (x, y + 2))

        val_txt = font_md.render(str(value), True, TEXT_BRIGHT)
        screen.blit(val_txt, (x + 90, y - 2))

        bar_x = x + 150
        bar_w = w - 180
        bar_h = 18
        pygame.draw.rect(screen, BAR_BG, (bar_x, y + 4, bar_w, bar_h), border_radius=4)

        if is_throttle:
            fill_pct = (value - RC_MIN) / (RC_MAX - RC_MIN)
            fill_w = int(bar_w * fill_pct)
            r = int(THROTTLE_LOW[0] + (THROTTLE_HIGH[0] - THROTTLE_LOW[0]) * fill_pct)
            g = int(THROTTLE_LOW[1] + (THROTTLE_HIGH[1] - THROTTLE_LOW[1]) * fill_pct)
            b = int(THROTTLE_LOW[2] + (THROTTLE_HIGH[2] - THROTTLE_LOW[2]) * fill_pct)
            if fill_w > 0:
                pygame.draw.rect(screen, (r, g, b),
                                 (bar_x, y + 4, fill_w, bar_h), border_radius=4)
        else:
            center_x = bar_x + bar_w // 2
            offset = raw * (bar_w // 2)
            if offset >= 0:
                pygame.draw.rect(screen, color,
                                 (center_x, y + 4, int(offset), bar_h), border_radius=4)
            else:
                pygame.draw.rect(screen, color,
                                 (center_x + int(offset), y + 4, -int(offset), bar_h),
                                 border_radius=4)
            pygame.draw.line(screen, TEXT_DIM, (center_x, y + 2), (center_x, y + bar_h + 6))

        pct_str = f"{abs(raw) * 100:.0f}%"
        pct_txt = font_sm.render(pct_str, True, TEXT_DIM)
        screen.blit(pct_txt, (bar_x + bar_w + 6, y + 4))

    def _draw_stick_viz(self, screen, cx, cy, size, dx, dy, label, color, fonts):
        """Draw a joystick position visualizer."""
        font_sm = fonts[0]

        pygame.draw.circle(screen, BAR_BG, (cx, cy), size)
        pygame.draw.circle(screen, PANEL_BORDER, (cx, cy), size, 1)
        pygame.draw.line(screen, PANEL_BORDER, (cx - size, cy), (cx + size, cy))
        pygame.draw.line(screen, PANEL_BORDER, (cx, cy - size), (cx, cy + size))

        sx = cx + int(dx * (size - 10))
        sy = cy + int(dy * (size - 10))
        pygame.draw.circle(screen, color, (sx, sy), 12)
        pygame.draw.circle(screen, TEXT_BRIGHT, (sx, sy), 12, 2)

        lbl = font_sm.render(label, True, TEXT_DIM)
        screen.blit(lbl, (cx - lbl.get_width() // 2, cy + size + 8))

    # ─── Main Loop ───────────────────────────────────────────────────────
    def run(self):
        """Main application entry point."""
        # Allow joystick events even when the window is not focused
        import os
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

        pygame.init()
        pygame.display.set_caption("Drone Controller — PS4")
        screen = pygame.display.set_mode((WIN_W, WIN_H))
        clock = pygame.time.Clock()

        # Fonts
        try:
            font_sm = pygame.font.SysFont("DejaVu Sans", 13)
            font_md = pygame.font.SysFont("DejaVu Sans", 16)
            font_lg = pygame.font.SysFont("DejaVu Sans", 22, bold=True)
            font_xl = pygame.font.SysFont("DejaVu Sans", 30, bold=True)
            font_icon = pygame.font.SysFont("DejaVu Sans", 40, bold=True)
        except Exception:
            font_sm = pygame.font.Font(None, 18)
            font_md = pygame.font.Font(None, 22)
            font_lg = pygame.font.Font(None, 28)
            font_xl = pygame.font.Font(None, 36)
            font_icon = pygame.font.Font(None, 46)
        fonts = (font_sm, font_md, font_lg, font_xl, font_icon)

        # Try to find the controller
        self.init_controller()

        # Controller reconnect timer
        reconnect_timer = 0

        # Start MAVLink threads (connect is manual via Square)
        threading.Thread(target=self.mavlink_send_loop, daemon=True).start()
        threading.Thread(target=self.mavlink_recv_loop, daemon=True).start()

        self.log("Ready. Press □ to connect, ✕ to arm, O to kill.")

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.shutdown()
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.shutdown()
                        pygame.quit()
                        sys.exit()
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == BTN_CIRCLE:
                        self.kill_motors()
                    elif event.button == BTN_CROSS:
                        self.log("Button X pressed (Arm Request)")
                        if not self.armed and self.connected and not self.killed:
                            self.arm_drone()
                    elif event.button == BTN_SQUARE:
                        self.log("Button Square pressed (Connect Request)")
                        if not self.connected and not self.connecting:
                            threading.Thread(target=self.mavlink_connect,
                                             daemon=True).start()
                elif event.type == pygame.JOYDEVICEADDED:
                    self.init_controller()
                elif event.type == pygame.JOYDEVICEREMOVED:
                    self.controller_connected = False
                    self.throttle = RC_MIN
                    self.raw_throttle = 0.0

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # UI button clicks
                    pos = event.pos
                    if self.btn_kill_rect.collidepoint(pos) and not self.killed:
                        self.kill_motors()
                    elif self.btn_disarm_rect.collidepoint(pos) and self.armed:
                        self.disarm_drone()
                    elif self.btn_arm_rect.collidepoint(pos):
                        if self.connected and not self.armed and not self.killed:
                            self.arm_drone()
                    elif self.btn_connect_rect.collidepoint(pos):
                        if not self.connected and not self.connecting:
                            threading.Thread(target=self.mavlink_connect,
                                             daemon=True).start()

            # Process continuous inputs
            if self.controller_connected and not self.killed:
                self.process_input()
            elif self.killed:
                self.throttle = RC_MIN
                self.raw_throttle = 0.0
                self.roll = RC_MID
                self.pitch = RC_MID
                self.yaw = RC_MID

            # Periodic controller reconnect
            if not self.controller_connected:
                reconnect_timer += 1
                if reconnect_timer > UI_FPS * 3:
                    self.init_controller()
                    reconnect_timer = 0

            # Render
            self.draw_ui(screen, fonts)
            pygame.display.flip()
            clock.tick(UI_FPS)

        pygame.quit()


def main():
    controller = DroneController()
    try:
        controller.run()
    except KeyboardInterrupt:
        controller.shutdown()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
