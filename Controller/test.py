#!/usr/bin/env python3

from pymavlink import mavutil
import time
import sys

DEVICE = "/dev/ttyACM0"   # change to /dev/serial0 if using UART
BAUD   = 115200           # ignored for USB, required for UART

print(f"Connecting to {DEVICE} ...")
master = mavutil.mavlink_connection(DEVICE, baud=BAUD)

# Wait for heartbeat from flight controller
print("Waiting for FC heartbeat...")
master.wait_heartbeat()
print(f"Heartbeat received from system {master.target_system} component {master.target_component}")

# Disable arming checks to make testing easier (optional, but helpful for debugging)
# print("Disabling arming checks...")
# master.mav.param_set_send(
#     master.target_system,
#     master.target_component,
#     b'ARMING_CHECK',
#     0,
#     mavutil.mavlink.MAV_PARAM_TYPE_INT32
# )

# Send GCS heartbeat repeatedly to keep connection alive
def send_gcs_heartbeat():
    master.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0, 0, 0
    )

# Send ARM command
print("Sending ARM command...")
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0,
    1,   # param1 = 1 → arm
    0, 0, 0, 0, 0, 0
)

# State variables
armed = False
last_heartbeat_time = time.time()

print("Monitoring FC messages... Press Ctrl+C to stop.")

try:
    while True:
        # 1. Send Heartbeat to keep GCS alive (1Hz)
        if time.time() - last_heartbeat_time > 1.0:
            send_gcs_heartbeat()
            last_heartbeat_time = time.time()

        # 2. Receive Messages
        try:
            msg = master.recv_match(blocking=False)
        except Exception as e:
            print(f"Error receiving message: {e}")
            continue

        if not msg:
            # 3. Send RC Override continuously (10Hz) - kept separate to run faster than heartbeat
            # Sending neutral values
            master.mav.rc_channels_override_send(
                master.target_system,
                master.target_component,
                1500,  # Ch1: Roll
                1500,  # Ch2: Pitch
                1100,  # Ch3: Throttle (Min + 100)
                1500,  # Ch4: Yaw
                2000,  # Ch5: AUX1 (Switch High = Arm)
                1000,  # Ch6
                1000,  # Ch7
                1000   # Ch8
            )
            time.sleep(0.01)
            continue

        msg_type = msg.get_type()
        print(f"[RAW] {msg}")  # Print everything raw as requested

        if msg_type == "STATUSTEXT":
            # Print important status messages from the FC (e.g. "Arming denied: ...")
            severity = msg.severity
            text = msg.text
            print(f"[FC] {text}")

        elif msg_type == "COMMAND_ACK":
            # Print command results (e.g. result of ARM command)
            cmd = msg.command
            result = msg.result
            result_str = {0: "ACCEPTED", 1: "TEMPORARILY_REJECTED", 2: "DENIED", 3: "UNSUPPORTED", 4: "FAILED", 5: "IN_PROGRESS", 6: "CANCELLED"}.get(result, f"UNKNOWN({result})")
            if cmd == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                print(f"[CMD] ARM/DISARM: {result_str}")
            else:
                print(f"[CMD] {cmd}: {result_str}")

        elif msg_type == "HEARTBEAT":
            is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if is_armed != armed:
                armed = is_armed
                status = "ARMED" if armed else "DISARMED"
                print(f"[sys] Vehicle is now {status}")

            # Also check system status for errors
            # system_status = msg.system_status

        elif msg_type == "SYS_STATUS":
             # Optional: Battery checks etc
             pass

except KeyboardInterrupt:
    print("\nStopping...")
    # Disarm on exit for safety
    print("Disarming...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        0, 0, 0, 0, 0, 0, 0  # param1 = 0 -> disarm
    )
    sys.exit(0)
