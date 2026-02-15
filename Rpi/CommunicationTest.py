#!/usr/bin/env python3
from pymavlink import mavutil
import time

print("Connecting to drone via UDP...")
# Listen on port 14550 for MAVLink messages from the Pi
master = mavutil.mavlink_connection('udpin:0.0.0.0:14550')

print("Waiting for heartbeat...")
master.wait_heartbeat()
print("✓ Heartbeat received!")
print(f"  System ID: {master.target_system}")
print(f"  Component ID: {master.target_component}")

print("\nListening for telemetry (press Ctrl+C to stop)...\n")

# Print some basic telemetry for 30 seconds
start_time = time.time()
while time.time() - start_time < 30:
    msg = master.recv_match(blocking=True, timeout=1)
    if msg:
        msg_type = msg.get_type()
        
        # Print some useful telemetry
        if msg_type == "HEARTBEAT":
            print(f"Heartbeat - Mode: {msg.custom_mode}, Armed: {msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED != 0}")
        
        elif msg_type == "SYS_STATUS":
            print(f"Battery: {msg.battery_remaining}%")
        
        elif msg_type == "ATTITUDE":
            print(f"Attitude - Roll: {msg.roll:.2f}, Pitch: {msg.pitch:.2f}, Yaw: {msg.yaw:.2f}")

print("\n✓ Communication test complete!")
