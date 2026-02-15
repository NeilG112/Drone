#!/usr/bin/env python3
from pymavlink import mavutil
import tkinter as tk
from tkinter import ttk
import threading

class DroneController:
    def __init__(self):
        self.master = None
        self.connected = False
        self.armed = False
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title("Drone Controller")
        self.root.geometry("400x300")
        
        # Connection status
        self.status_label = tk.Label(self.root, text="Disconnected", fg="red", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
        # Arm/Disarm button
        self.arm_button = tk.Button(
            self.root, 
            text="ARM", 
            command=self.toggle_arm,
            bg="green",
            fg="white",
            font=("Arial", 16),
            width=15,
            height=2,
            state=tk.DISABLED
        )
        self.arm_button.pack(pady=20)
        
        # Throttle slider
        tk.Label(self.root, text="Throttle", font=("Arial", 12)).pack(pady=5)
        self.throttle_value_label = tk.Label(self.root, text="1000", font=("Arial", 12))
        self.throttle_value_label.pack()
        
        self.throttle_slider = tk.Scale(
            self.root,
            from_=1000,
            to=2000,
            orient=tk.HORIZONTAL,
            length=300,
            command=self.update_throttle,
            state=tk.DISABLED
        )
        self.throttle_slider.set(1000)
        self.throttle_slider.pack(pady=10)
        
        # Start connection in background thread
        self.connect_thread = threading.Thread(target=self.connect_to_drone, daemon=True)
        self.connect_thread.start()
        
    def connect_to_drone(self):
        try:
            print("Connecting to drone...")
            self.master = mavutil.mavlink_connection('udpin:0.0.0.0:14550')
            print("Waiting for heartbeat...")
            self.master.wait_heartbeat()
            print("Connected!")
            
            self.connected = True
            self.status_label.config(text="Connected", fg="green")
            self.arm_button.config(state=tk.NORMAL)
            self.throttle_slider.config(state=tk.NORMAL)
            
        except Exception as e:
            print(f"Connection error: {e}")
            self.status_label.config(text=f"Error: {e}", fg="red")
    
    def toggle_arm(self):
        if not self.connected:
            return
            
        if not self.armed:
            # Arm
            print("Arming...")
            self.master.arducopter_arm()
            self.master.motors_armed_wait()
            self.armed = True
            self.arm_button.config(text="DISARM", bg="red")
            print("Armed!")
        else:
            # Disarm
            print("Disarming...")
            self.master.arducopter_disarm()
            self.master.motors_disarmed_wait()
            self.armed = False
            self.arm_button.config(text="ARM", bg="green")
            self.throttle_slider.set(1000)  # Reset throttle
            print("Disarmed!")
    
    def update_throttle(self, value):
        if not self.connected:
            return
        
        throttle = int(float(value))
        self.throttle_value_label.config(text=str(throttle))
        
        # Send RC override command (channel 3 is throttle)
        self.master.mav.rc_channels_override_send(
            self.master.target_system,
            self.master.target_component,
            0,        # channel 1 (roll)
            0,        # channel 2 (pitch)
            throttle, # channel 3 (throttle)
            0,        # channel 4 (yaw)
            0, 0, 0, 0  # channels 5-8
        )
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    controller = DroneController()
    controller.run()