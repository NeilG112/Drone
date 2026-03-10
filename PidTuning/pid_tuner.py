#!/usr/bin/env python3
"""
PID Tuner — Betaflight via MAVLink
Pygame GUI with sliders for all PID gains (Roll/Pitch/Yaw P/I/D)
and a throttle-only slider for motor testing.

Usage:
  python3 pid_tuner.py
"""

import sys
import time
import math
import threading
from collections import deque

import pygame
from pymavlink import mavutil

# ─── Configuration ────────────────────────────────────────────────────────────
SERIAL_PORT = "/dev/ttyACM0"
BAUD = 115200

RC_MIN = 1000
RC_MAX = 2000
RC_MID = 1500

SEND_RATE_HZ = 20
UI_FPS = 30

# ─── Colors ───────────────────────────────────────────────────────────────────
BG_COLOR       = (14, 14, 20)
PANEL_BG       = (24, 24, 34)
PANEL_BORDER   = (44, 44, 58)
TEXT_DIM       = (100, 100, 120)
TEXT_NORMAL    = (180, 180, 200)
TEXT_BRIGHT    = (235, 235, 250)
ACCENT_BLUE    = (60, 120, 255)
ACCENT_GREEN   = (40, 200, 110)
ACCENT_RED     = (255, 55, 70)
ACCENT_ORANGE  = (255, 160, 40)
ACCENT_PURPLE  = (140, 90, 255)
ACCENT_CYAN    = (0, 200, 220)
ACCENT_YELLOW  = (255, 210, 50)
ACCENT_PINK    = (255, 100, 160)
BAR_BG         = (36, 36, 50)
BTN_HOVER      = (50, 50, 68)
THROTTLE_LOW   = (40, 200, 110)
THROTTLE_HIGH  = (255, 55, 70)
KILL_FLASH     = (200, 30, 40)
SLIDER_TRACK   = (50, 50, 68)
SLIDER_GROOVE  = (30, 30, 42)

# ─── Window ───────────────────────────────────────────────────────────────────
WIN_W, WIN_H = 1200, 820

# ─── PID Parameter Definitions ────────────────────────────────────────────────
# Each entry: (display_name, param_name, min_val, max_val, default, step)
PID_PARAMS = [
    # Roll
    ("Roll P",  "ATC_RAT_RLL_P", 0.0, 2.0, 0.135, 0.001),
    ("Roll I",  "ATC_RAT_RLL_I", 0.0, 1.0, 0.135, 0.001),
    ("Roll D",  "ATC_RAT_RLL_D", 0.0, 0.1, 0.003, 0.0001),
    # Pitch
    ("Pitch P", "ATC_RAT_PIT_P", 0.0, 2.0, 0.135, 0.001),
    ("Pitch I", "ATC_RAT_PIT_I", 0.0, 1.0, 0.135, 0.001),
    ("Pitch D", "ATC_RAT_PIT_D", 0.0, 0.1, 0.003, 0.0001),
    # Yaw
    ("Yaw P",   "ATC_RAT_YAW_P", 0.0, 2.0, 0.180, 0.001),
    ("Yaw I",   "ATC_RAT_YAW_I", 0.0, 1.0, 0.018, 0.001),
    ("Yaw D",   "ATC_RAT_YAW_D", 0.0, 0.1, 0.0,   0.0001),
]

# Group names and which PID_PARAMS indices belong to each group
PID_GROUPS = [
    ("ROLL",  [0, 1, 2], ACCENT_BLUE),
    ("PITCH", [3, 4, 5], ACCENT_GREEN),
    ("YAW",   [6, 7, 8], ACCENT_PURPLE),
]


class Slider:
    """A draggable horizontal slider widget."""

    def __init__(self, x, y, w, h, min_val, max_val, value, step, label,
                 color, param_name=""):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self.step = step
        self.label = label
        self.color = color
        self.param_name = param_name
        self.dragging = False
        self.knob_radius = 10
        self.changed = False  # set True when user releases after dragging

    @property
    def knob_x(self):
        if self.max_val == self.min_val:
            return self.rect.x
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        return int(self.rect.x + ratio * self.rect.w)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            knob_rect = pygame.Rect(
                self.knob_x - self.knob_radius,
                self.rect.y - self.knob_radius + self.rect.h // 2,
                self.knob_radius * 2,
                self.knob_radius * 2
            )
            # Also allow clicking on the track
            expanded = self.rect.inflate(0, 16)
            if knob_rect.collidepoint(event.pos) or expanded.collidepoint(event.pos):
                self.dragging = True
                self._update_value(event.pos[0])

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                self.changed = True

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self._update_value(event.pos[0])

    def _update_value(self, mouse_x):
        rel = (mouse_x - self.rect.x) / max(1, self.rect.w)
        rel = max(0.0, min(1.0, rel))
        raw = self.min_val + rel * (self.max_val - self.min_val)
        # Snap to step
        if self.step > 0:
            raw = round(raw / self.step) * self.step
        self.value = max(self.min_val, min(self.max_val, raw))

    def draw(self, screen, fonts):
        font_sm, font_md = fonts[0], fonts[1]

        # Label
        lbl = font_sm.render(self.label, True, TEXT_NORMAL)
        screen.blit(lbl, (self.rect.x, self.rect.y - 18))

        # Value text
        if self.max_val >= 10:
            val_str = f"{self.value:.0f}"
        elif self.max_val >= 1:
            val_str = f"{self.value:.3f}"
        else:
            val_str = f"{self.value:.4f}"
        val_txt = font_md.render(val_str, True, TEXT_BRIGHT)
        screen.blit(val_txt, (self.rect.x + self.rect.w + 12, self.rect.y - 4))

        # Track groove
        track_y = self.rect.y + self.rect.h // 2
        pygame.draw.rect(screen, SLIDER_GROOVE,
                         (self.rect.x, track_y - 3, self.rect.w, 6),
                         border_radius=3)

        # Filled portion
        kx = self.knob_x
        fill_w = kx - self.rect.x
        if fill_w > 0:
            pygame.draw.rect(screen, self.color,
                             (self.rect.x, track_y - 3, fill_w, 6),
                             border_radius=3)

        # Knob
        knob_color = TEXT_BRIGHT if self.dragging else self.color
        pygame.draw.circle(screen, knob_color, (kx, track_y), self.knob_radius)
        pygame.draw.circle(screen, TEXT_BRIGHT, (kx, track_y), self.knob_radius, 2)

        # Glow when dragging
        if self.dragging:
            glow = pygame.Surface((self.knob_radius * 4, self.knob_radius * 4),
                                  pygame.SRCALPHA)
            pygame.draw.circle(glow, (*self.color, 40),
                               (self.knob_radius * 2, self.knob_radius * 2),
                               self.knob_radius * 2)
            screen.blit(glow, (kx - self.knob_radius * 2,
                               track_y - self.knob_radius * 2))


class PIDTuner:
    """PID Tuning application with MAVLink + pygame GUI."""

    def __init__(self):
        # RC channel — only throttle is user-controlled
        self.throttle = RC_MIN

        # State
        self.running = True
        self.armed = False
        self.killed = False
        self.connected = False
        self.connecting = False
        self.master = None

        # MAVLink timing
        self.last_heartbeat_time = 0

        # Logs
        self.logs = deque(maxlen=18)

        # Kill flash
        self.kill_flash_time = 0

        # Parameter cache {param_name: value}
        self.fc_params = {}
        self.params_loaded = False

        # UI button rects
        self.btn_connect_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_arm_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_disarm_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_kill_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_save_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_refresh_rect = pygame.Rect(0, 0, 0, 0)

        # Sliders — created during init_ui
        self.pid_sliders = []
        self.throttle_slider = None

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {msg}")

    # ─── MAVLink ──────────────────────────────────────────────────────────

    def mavlink_connect(self):
        """Connect to flight controller."""
        if self.connected or self.connecting:
            self.log("Already connected or connecting...")
            return

        self.killed = False
        self.throttle = RC_MIN
        self.connecting = True

        try:
            self.log(f"Connecting to {SERIAL_PORT}...")
            self.master = mavutil.mavlink_connection(SERIAL_PORT, baud=BAUD)
            self.log("Waiting for FC heartbeat...")
            self.master.wait_heartbeat(timeout=10)
            self.connected = True
            self.log(f"FC connected (sys={self.master.target_system} "
                     f"comp={self.master.target_component})")
            self.last_heartbeat_time = time.time()

            # Request all parameters
            self.request_params()
        except Exception as e:
            self.log(f"Connection failed: {e}")
            self.connected = False
        finally:
            self.connecting = False

    def request_params(self):
        """Request all parameters from FC."""
        if self.master and self.connected:
            try:
                self.log("Requesting parameters from FC...")
                self.master.mav.param_request_list_send(
                    self.master.target_system,
                    self.master.target_component
                )
            except Exception as e:
                self.log(f"Param request failed: {e}")

    def set_param(self, param_name, value):
        """Send a parameter value to the FC."""
        if not self.master or not self.connected:
            self.log("Cannot set param: not connected")
            return
        try:
            # Encode param name as bytes (max 16 chars)
            name_bytes = param_name.encode('utf-8')
            self.master.mav.param_set_send(
                self.master.target_system,
                self.master.target_component,
                name_bytes,
                float(value),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
            self.log(f"Set {param_name} = {value:.4f}")
        except Exception as e:
            self.log(f"Set param failed: {e}")

    def send_gcs_heartbeat(self):
        """Send GCS heartbeat to keep connection alive (~1 Hz)."""
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
        """Read FC messages in background thread."""
        while self.running:
            if not self.master or not self.connected:
                time.sleep(0.1)
                continue

            # GCS heartbeat at 1 Hz
            now = time.time()
            if now - self.last_heartbeat_time > 1.0:
                self.send_gcs_heartbeat()
                self.last_heartbeat_time = now

            try:
                msg = self.master.recv_match(blocking=False)
            except Exception:
                time.sleep(0.01)
                continue

            if not msg:
                time.sleep(0.01)
                continue

            msg_type = msg.get_type()

            if msg_type == "PARAM_VALUE":
                name = msg.param_id.strip('\x00')
                val = msg.param_value
                self.fc_params[name] = val
                # Update matching slider
                for slider in self.pid_sliders:
                    if slider.param_name == name:
                        slider.value = max(slider.min_val,
                                           min(slider.max_val, val))
                        self.log(f"← {name} = {val:.4f}")

            elif msg_type == "STATUSTEXT":
                self.log(f"[FC] {msg.text}")

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
                is_armed = bool(
                    msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if is_armed != self.armed:
                    self.armed = is_armed
                    status = "ARMED" if self.armed else "DISARMED"
                    self.log(f"[FC] Vehicle is now {status}")
                    if not self.armed:
                        self.killed = False

            time.sleep(0.01)

    def mavlink_send_loop(self):
        """Send RC override at fixed rate. Only throttle is user-controlled."""
        while self.running:
            if self.master and self.connected and not self.killed:
                try:
                    aux1 = 2000 if self.armed else 1000
                    self.master.mav.rc_channels_override_send(
                        self.master.target_system,
                        self.master.target_component,
                        RC_MID,          # ch1: Roll (centered)
                        RC_MID,          # ch2: Pitch (centered)
                        self.throttle,   # ch3: Throttle
                        RC_MID,          # ch4: Yaw (centered)
                        aux1,            # ch5: AUX1 (Arm switch)
                        1000,            # ch6
                        1000,            # ch7
                        1000             # ch8
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
                0, 1, 0, 0, 0, 0, 0, 0
            )
        except Exception as e:
            self.log(f"Arm failed: {e}")

    def disarm_drone(self):
        if not self.master or not self.connected:
            self.log("Cannot disarm: not connected")
            return
        if not self.armed:
            self.log("Already disarmed")
            return
        try:
            self.log("Sending DISARM command...")
            self.throttle = RC_MIN
            if self.throttle_slider:
                self.throttle_slider.value = RC_MIN
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 0, 0, 0, 0, 0, 0, 0
            )
        except Exception as e:
            self.log(f"Disarm failed: {e}")

    def kill_motors(self):
        if self.killed:
            return
        self.log("!!! KILL SWITCH ACTIVATED !!!")
        self.throttle = RC_MIN
        if self.throttle_slider:
            self.throttle_slider.value = RC_MIN
        self.killed = True
        self.armed = False
        self.kill_flash_time = time.time()

        if self.master and self.connected:
            try:
                self.master.mav.rc_channels_override_send(
                    self.master.target_system,
                    self.master.target_component,
                    RC_MID, RC_MID, RC_MIN, RC_MID,
                    0, 0, 0, 0
                )
                self.master.mav.command_long_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0, 0, 21196, 0, 0, 0, 0, 0
                )
                self.log("FORCE DISARM SENT")
            except Exception as e:
                self.log(f"Kill error: {e}")

    def shutdown(self):
        self.kill_motors()
        self.running = False
        if self.master:
            try:
                self.master.arducopter_disarm()
            except Exception:
                pass
        self.log("Shutdown complete")

    # ─── UI Helpers ───────────────────────────────────────────────────────

    def _draw_panel(self, screen, x, y, w, h, title, fonts, title_color=None):
        font_sm = fonts[0]
        pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=10)
        pygame.draw.rect(screen, PANEL_BORDER, (x, y, w, h), 1, border_radius=10)
        tc = title_color if title_color else TEXT_DIM
        ttl = font_sm.render(title, True, tc)
        screen.blit(ttl, (x + 14, y + 10))

    def _draw_button(self, screen, x, y, w, h, label, color, enabled, fonts):
        font_md = fonts[1]
        rect = pygame.Rect(x, y, w, h)
        if enabled:
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

    # ─── Main UI Drawing ─────────────────────────────────────────────────

    def draw_ui(self, screen, fonts):
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

        # ─── Header ──────────────────────────────────────────────────
        pygame.draw.rect(screen, PANEL_BG, (0, 0, WIN_W, 52))
        pygame.draw.line(screen, PANEL_BORDER, (0, 52), (WIN_W, 52))

        title = font_lg.render("⚙  PID TUNER", True, TEXT_BRIGHT)
        screen.blit(title, (18, 12))

        # Status badges
        badge_x = WIN_W - 16
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

        for label, color in reversed(badges):
            tw = font_sm.size(label)[0]
            bw = tw + 16
            badge_x -= bw + 8
            pygame.draw.rect(screen, (*color, 30) if len(color) == 3 else color,
                             (badge_x, 14, bw, 24), border_radius=12)
            pygame.draw.rect(screen, color,
                             (badge_x, 14, bw, 24), 1, border_radius=12)
            txt = font_sm.render(label, True, color)
            screen.blit(txt, (badge_x + 8, 18))

        y_top = 64

        # ─── Left Column: PID Sliders ────────────────────────────────
        pid_panel_x = 16
        pid_panel_w = 720
        pid_panel_h = 520
        self._draw_panel(screen, pid_panel_x, y_top, pid_panel_w, pid_panel_h,
                         "PID PARAMETERS", fonts)

        # Group headers + sliders
        group_y = y_top + 34
        for group_name, indices, group_color in PID_GROUPS:
            # Group header with accent line
            pygame.draw.rect(screen, group_color,
                             (pid_panel_x + 16, group_y + 2, 4, 14),
                             border_radius=2)
            grp_lbl = font_md.render(group_name, True, group_color)
            screen.blit(grp_lbl, (pid_panel_x + 28, group_y))

            # Draw the 3 sliders for this group
            slider_y = group_y + 28
            for idx in indices:
                self.pid_sliders[idx].rect.y = slider_y + 18
                self.pid_sliders[idx].rect.x = pid_panel_x + 100
                self.pid_sliders[idx].rect.w = 480
                self.pid_sliders[idx].draw(screen, fonts)
                slider_y += 52

            group_y = slider_y + 10

        # ─── Right Column: Throttle + Actions ────────────────────────
        right_x = pid_panel_x + pid_panel_w + 16
        right_w = WIN_W - right_x - 16

        # Throttle panel
        throttle_panel_h = 140
        self._draw_panel(screen, right_x, y_top, right_w, throttle_panel_h,
                         "THROTTLE (RC3)", fonts, ACCENT_RED)

        self.throttle_slider.rect.x = right_x + 20
        self.throttle_slider.rect.y = y_top + 58
        self.throttle_slider.rect.w = right_w - 110
        self.throttle_slider.draw(screen, fonts)

        # Throttle bar visualization
        bar_x = right_x + 20
        bar_y = y_top + 100
        bar_w = right_w - 40
        bar_h = 20
        pygame.draw.rect(screen, BAR_BG, (bar_x, bar_y, bar_w, bar_h),
                         border_radius=4)
        fill_pct = (self.throttle - RC_MIN) / (RC_MAX - RC_MIN)
        fill_w = int(bar_w * fill_pct)
        r = int(THROTTLE_LOW[0] + (THROTTLE_HIGH[0] - THROTTLE_LOW[0]) * fill_pct)
        g = int(THROTTLE_LOW[1] + (THROTTLE_HIGH[1] - THROTTLE_LOW[1]) * fill_pct)
        b = int(THROTTLE_LOW[2] + (THROTTLE_HIGH[2] - THROTTLE_LOW[2]) * fill_pct)
        if fill_w > 0:
            pygame.draw.rect(screen, (r, g, b),
                             (bar_x, bar_y, fill_w, bar_h), border_radius=4)

        # Actions panel
        action_y = y_top + throttle_panel_h + 16
        action_h = 190
        self._draw_panel(screen, right_x, action_y, right_w, action_h,
                         "ACTIONS", fonts)

        btn_w = (right_w - 48) // 2
        btn_h = 40
        bx1 = right_x + 16
        bx2 = bx1 + btn_w + 16

        # Row 1: Connect / Arm
        by = action_y + 38
        connect_color = ACCENT_BLUE if not self.connected else TEXT_DIM
        connect_label = "CONNECT" if not self.connected else "CONNECTED"
        self.btn_connect_rect = self._draw_button(
            screen, bx1, by, btn_w, btn_h, connect_label,
            connect_color, not self.connected and not self.connecting, fonts)

        arm_color = ACCENT_GREEN if not self.armed else TEXT_DIM
        arm_label = "ARM" if not self.armed else "ARMED"
        can_arm = self.connected and not self.armed and not self.killed
        self.btn_arm_rect = self._draw_button(
            screen, bx2, by, btn_w, btn_h, arm_label,
            arm_color, can_arm, fonts)

        # Row 2: Disarm / Kill
        by += btn_h + 12
        can_disarm = self.armed and not self.killed
        self.btn_disarm_rect = self._draw_button(
            screen, bx1, by, btn_w, btn_h, "DISARM",
            ACCENT_ORANGE, can_disarm, fonts)

        self.btn_kill_rect = self._draw_button(
            screen, bx2, by, btn_w, btn_h, "KILL",
            ACCENT_RED, not self.killed, fonts)

        # Row 3: Refresh Params / Save
        by += btn_h + 12
        self.btn_refresh_rect = self._draw_button(
            screen, bx1, by, btn_w, btn_h, "REFRESH",
            ACCENT_CYAN, self.connected, fonts)

        self.btn_save_rect = self._draw_button(
            screen, bx2, by, btn_w, btn_h, "SEND ALL",
            ACCENT_YELLOW, self.connected, fonts)

        # ─── Info panel (right column below actions) ─────────────────
        info_y = action_y + action_h + 16
        info_h = pid_panel_h - throttle_panel_h - action_h - 32
        if info_h > 60:
            self._draw_panel(screen, right_x, info_y, right_w, info_h,
                             "RC OUTPUT", fonts)
            ch_data = [
                ("THR", self.throttle, ACCENT_RED),
                ("ROLL", RC_MID, ACCENT_BLUE),
                ("PITCH", RC_MID, ACCENT_GREEN),
                ("YAW", RC_MID, ACCENT_PURPLE),
            ]
            cy = info_y + 34
            for ch_name, ch_val, ch_color in ch_data:
                lbl = font_sm.render(f"{ch_name}:", True, TEXT_DIM)
                screen.blit(lbl, (right_x + 16, cy))
                val = font_md.render(str(ch_val), True, ch_color)
                screen.blit(val, (right_x + 70, cy - 2))
                cy += 24

        # ─── Bottom: Event Log ────────────────────────────────────────
        log_y = y_top + pid_panel_h + 16
        log_h = WIN_H - log_y - 16
        self._draw_panel(screen, 16, log_y, WIN_W - 32, log_h,
                         "EVENT LOG", fonts)

        ly = log_y + 30
        for msg in list(self.logs):
            if ly + 16 > log_y + log_h - 8:
                break
            color = TEXT_DIM
            if "KILL" in msg or "FORCE" in msg:
                color = ACCENT_RED
            elif "ARMED" in msg or "✓" in msg:
                color = ACCENT_GREEN
            elif "Error" in msg or "failed" in msg:
                color = ACCENT_ORANGE
            elif "Connect" in msg or "connect" in msg:
                color = ACCENT_CYAN
            elif "DISARM" in msg:
                color = ACCENT_ORANGE
            elif "Set " in msg or "←" in msg:
                color = ACCENT_YELLOW
            txt = font_sm.render(msg, True, color)
            screen.blit(txt, (32, ly))
            ly += 18

    # ─── Main Loop ────────────────────────────────────────────────────────

    def run(self):
        pygame.init()
        pygame.display.set_caption("PID Tuner — Betaflight via MAVLink")
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

        # Create PID sliders
        for i, (display_name, param_name, min_v, max_v, default, step) in \
                enumerate(PID_PARAMS):
            # Find group color
            color = TEXT_NORMAL
            for _, indices, gc in PID_GROUPS:
                if i in indices:
                    color = gc
                    break
            slider = Slider(
                x=100, y=100, w=480, h=12,
                min_val=min_v, max_val=max_v, value=default, step=step,
                label=display_name, color=color, param_name=param_name
            )
            self.pid_sliders.append(slider)

        # Create throttle slider
        self.throttle_slider = Slider(
            x=100, y=100, w=300, h=12,
            min_val=RC_MIN, max_val=RC_MAX, value=RC_MIN, step=1,
            label="THROTTLE", color=ACCENT_RED
        )

        # Start MAVLink threads
        threading.Thread(target=self.mavlink_recv_loop, daemon=True).start()
        threading.Thread(target=self.mavlink_send_loop, daemon=True).start()

        self.log("Ready. Click CONNECT to link to FC.")
        self.log("Adjust PID sliders → values sent on release.")
        self.log("Throttle controls RC Ch3 only.")

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
                    elif event.key == pygame.K_k:
                        self.kill_motors()

                # Pass events to sliders
                for slider in self.pid_sliders:
                    slider.handle_event(event)
                self.throttle_slider.handle_event(event)

                # Mouse clicks on buttons
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos
                    if self.btn_kill_rect.collidepoint(pos) and not self.killed:
                        self.kill_motors()
                    elif (self.btn_disarm_rect.collidepoint(pos)
                          and self.armed and not self.killed):
                        self.disarm_drone()
                    elif self.btn_arm_rect.collidepoint(pos):
                        if (self.connected and not self.armed
                                and not self.killed):
                            self.arm_drone()
                    elif self.btn_connect_rect.collidepoint(pos):
                        if not self.connected and not self.connecting:
                            threading.Thread(target=self.mavlink_connect,
                                             daemon=True).start()
                    elif (self.btn_refresh_rect.collidepoint(pos)
                          and self.connected):
                        self.request_params()
                    elif (self.btn_save_rect.collidepoint(pos)
                          and self.connected):
                        self.log("Sending all PID values to FC...")
                        for slider in self.pid_sliders:
                            self.set_param(slider.param_name, slider.value)

            # Check if any PID slider changed (released after drag)
            for slider in self.pid_sliders:
                if slider.changed:
                    slider.changed = False
                    if self.connected:
                        self.set_param(slider.param_name, slider.value)

            # Update throttle from slider
            if not self.killed:
                self.throttle = int(self.throttle_slider.value)
            else:
                self.throttle = RC_MIN
                self.throttle_slider.value = RC_MIN

            # Draw
            self.draw_ui(screen, fonts)
            pygame.display.flip()
            clock.tick(UI_FPS)


def main():
    app = PIDTuner()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()
        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    main()
