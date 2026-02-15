# 🚁 Drone Flight Testing

PS4 controller-based drone control system using **MAVLink** over **ArduPilot**. All control software runs on a laptop — the Raspberry Pi sits on the drone and forwards MAVLink traffic over the network.

## Architecture

Two connection modes are supported:

**USB Direct** — Laptop plugged directly into the flight controller (for bench testing):
```
PS4 Controller → Laptop (pygame UI) → USB → Flight Controller (ArduPilot)
```

**Network via RPi** — Laptop communicates wirelessly through the onboard RPi:
```
PS4 Controller → Laptop (pygame UI) → WiFi/UDP:14550 → Raspberry Pi → UART/USB → Flight Controller (ArduPilot)
```

## Project Structure

```
├── Controller/                     # USB direct connection mode
│   ├── ps4_drone_controller.py     # Full PS4 controller with pygame UI (serial)
│   └── test.py                     # MAVLink arm/disarm + RC override test
│
├── Rpi/                            # Network connection mode (via onboard RPi)
│   ├── PS4_Rpi.py                  # Full PS4 controller with pygame UI (UDP)
│   ├── ThrottleTest.py             # Simple arm + throttle slider (tkinter, UDP)
│   └── CommunicationTest.py        # Heartbeat & telemetry listener (UDP)
```

### `Controller/` — USB Direct

Scripts connect to the flight controller over USB serial (`/dev/ttyACM0` at 115200 baud). Used for bench testing with the laptop physically connected to the FC.

- **`ps4_drone_controller.py`** — Full PS4 controller with real-time pygame UI showing RC channels, stick positions, arm status, and logs.
- **`test.py`** — Headless test script: arms the drone, sends RC overrides, and prints all MAVLink messages. Press Ctrl+C to disarm and exit.

### `Rpi/` — Network via Raspberry Pi

Scripts connect over UDP (`udpin:0.0.0.0:14550`). The RPi on the drone bridges MAVLink between the FC and the laptop over WiFi.

- **`PS4_Rpi.py`** — Same full PS4 controller + pygame UI as above, but connects via UDP instead of serial.
- **`ThrottleTest.py`** — Minimal tkinter GUI with arm/disarm button and throttle slider.
- **`CommunicationTest.py`** — Connects, prints heartbeat/attitude/battery telemetry for 30 seconds, then exits.

## PS4 Controls

| Input              | Function                  |
| ------------------ | ------------------------- |
| **R2**             | Throttle (proportional)   |
| **Left Stick X**   | Yaw                       |
| **Left Stick Y**   | Pitch                     |
| **Right Stick X**  | Roll                      |
| **✕ (Cross)**      | Arm                       |
| **○ (Circle)**     | Kill (emergency disarm)   |
| **□ (Square)**     | Connect to FC             |
| **L1 / R1**        | Yaw trim left / right     |

## Requirements

```bash
pip install pymavlink pygame
```

- **pymavlink** — MAVLink protocol
- **pygame** — Controller input & UI
- **tkinter** — Built-in with Python (used by `ThrottleTest.py` only)

## Usage

```bash
# USB direct (laptop connected to FC)
python3 Controller/ps4_drone_controller.py
python3 Controller/test.py

# Via RPi network bridge
python3 Rpi/CommunicationTest.py   # verify connection first
python3 Rpi/ThrottleTest.py        # quick throttle test
python3 Rpi/PS4_Rpi.py             # full controller
```

## ⚠️ Safety

- Always test with **propellers removed**
- **○ (Circle)** is a kill switch — force-disarms regardless of flight state
- Throttle resets to minimum (1000) on startup and after disarming
- Ctrl+C sends a disarm command before exiting
