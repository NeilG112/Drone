# 🚁 Drone Flight Testing

A PS4 controller-based drone control system using **MAVLink** protocol, designed for a **Raspberry Pi + Betaflight** flight controller setup.

## Architecture

```
┌──────────────┐     Bluetooth      ┌──────────────┐    USB/UART    ┌──────────────┐
│  PS4 DualShock│ ──────────────────▸│ Raspberry Pi │ ─────────────▸│ Flight       │
│  Controller   │                    │  (MAVLink)   │               │ Controller   │
└──────────────┘                    └──────────────┘    MAVLink     │ (Betaflight) │
                                          │                         └──────────────┘
                                          │ UDP 14550
                                          ▼
                                    ┌──────────────┐
                                    │   Laptop     │
                                    │  (Monitor)   │
                                    └──────────────┘
```

## Project Structure

```
├── Controller/          # Laptop-side scripts
│   ├── ps4_drone_controller.py   # Full PS4 → drone controller with pygame UI
│   └── test.py                   # MAVLink test script (arm/disarm + RC override)
│
├── Rpi/                 # Raspberry Pi-side scripts
│   ├── PS4_Rpi.py                # PS4 controller app running directly on the Pi
│   ├── ThrottleTest.py           # Simple throttle test with tkinter GUI
│   └── CommunicationTest.py      # Basic MAVLink communication test
```

## Components

### Controller (Laptop)

- **`ps4_drone_controller.py`** — Full-featured PS4 controller interface with a real-time **pygame** UI. Reads controller input, translates it to MAVLink RC override commands, and displays live channel values, stick positions, armed status, and flight logs.
- **`test.py`** — Standalone MAVLink test script that connects directly to the flight controller via USB (`/dev/ttyACM0`), sends arm commands, and continuously streams RC override values. Useful for verifying the MAVLink connection without the PS4 controller.

### Raspberry Pi

- **`PS4_Rpi.py`** — Same PS4-to-drone controller as the laptop version, but configured to run on the Raspberry Pi with a direct serial connection to the flight controller.
- **`ThrottleTest.py`** — Minimal **tkinter** GUI with an arm/disarm button and a throttle slider. Connects via UDP on port `14550` and sends RC override commands. Great for quick throttle testing.
- **`CommunicationTest.py`** — Lightweight script that connects via UDP, waits for a heartbeat, and prints telemetry (attitude, battery, heartbeat) for 30 seconds to verify communication.

## Controls (PS4 Controller)

| Input         | Function                        |
| ------------- | ------------------------------- |
| **R2**        | Throttle (proportional)         |
| **Left Stick X** | Yaw                          |
| **Left Stick Y** | Pitch                        |
| **Right Stick X** | Roll                        |
| **✕ (Cross)** | Arm                            |
| **○ (Circle)** | Kill (emergency disarm)       |
| **□ (Square)** | Connect to flight controller   |
| **L1 / R1**   | Yaw trim left / right          |

## Requirements

### Python Dependencies

```bash
pip install pymavlink pygame
```

- **`pymavlink`** — MAVLink protocol library
- **`pygame`** — Controller input & real-time UI (for `ps4_drone_controller.py` / `PS4_Rpi.py`)
- **`tkinter`** — Built-in with Python (for `ThrottleTest.py`)

### Hardware

- Raspberry Pi (3/4/5)
- Flight controller running **Betaflight** with MAVLink enabled
- PS4 DualShock 4 controller (connected via Bluetooth)
- USB or UART connection between the Pi and the flight controller

## Usage

### On the Raspberry Pi

```bash
# Test communication first
python3 Rpi/CommunicationTest.py

# Quick throttle test
python3 Rpi/ThrottleTest.py

# Full PS4 controller
python3 Rpi/PS4_Rpi.py
```

### On the Laptop (connected via USB)

```bash
# Test MAVLink connection
python3 Controller/test.py

# Full PS4 controller UI
python3 Controller/ps4_drone_controller.py
```

## ⚠️ Safety

- Always test with propellers removed first
- The **○ (Circle)** button is an emergency kill switch — it force-disarms regardless of flight state
- Throttle defaults to minimum (1000) on startup and after disarming
- The system sends a disarm command on shutdown (Ctrl+C)
