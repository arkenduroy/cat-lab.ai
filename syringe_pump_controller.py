#!/usr/bin/env python3
"""
ISPLab02 Syringe Pump Controller
Automation script for controlling ISPLab02 syringe pump via serial communication
"""

import serial
import time
import sys
from enum import Enum
from typing import Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PumpMode(Enum):
    """Four working modes of ISPLab02"""
    INFUSION = 1
    WITHDRAWAL = 2
    INFUSION_WITHDRAWAL = 3
    WITHDRAWAL_INFUSION = 4


class ISPLab02Controller:
    """Controller class for ISPLab02 Syringe Pump"""
    
    def __init__(self, port: str = '/dev/tty.usbserial', baudrate: int = 9600):
        """
        Initialize pump controller
        
        Args:
            port: Serial port (e.g., '/dev/tty.usbserial' or '/dev/cu.usbserial')
            baudrate: Communication speed (default 9600)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_connected = False
        
    def connect(self) -> bool:
        """Establish serial connection with pump"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0
            )
            self.is_connected = True
            logger.info(f"Connected to pump on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial_conn and self.is_connected:
            self.serial_conn.close()
            self.is_connected = False
            logger.info("Disconnected from pump")
    
    def send_command(self, command: str) -> Optional[str]:
        """
        Send command to pump and read response
        
        Args:
            command: Command string to send
            
        Returns:
            Response from pump or None if error
        """
        if not self.is_connected:
            logger.error("Not connected to pump")
            return None
        
        try:
            # Add carriage return and line feed if not present
            if not command.endswith('\r\n'):
                command += '\r\n'
            
            # Send command
            self.serial_conn.write(command.encode('ascii'))
            logger.debug(f"Sent: {command.strip()}")
            
            # Read response
            time.sleep(0.1)  # Small delay for pump to process
            response = self.serial_conn.readline().decode('ascii').strip()
            logger.debug(f"Received: {response}")
            
            return response
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return None
    
    def set_mode(self, mode: PumpMode) -> bool:
        """
        Set pump operating mode
        
        Args:
            mode: One of the four PumpMode options
        """
        mode_commands = {
            PumpMode.INFUSION: "MODE:INF",
            PumpMode.WITHDRAWAL: "MODE:WDR", 
            PumpMode.INFUSION_WITHDRAWAL: "MODE:I/W",
            PumpMode.WITHDRAWAL_INFUSION: "MODE:W/I"
        }
        
        command = mode_commands.get(mode)
        if command:
            response = self.send_command(command)
            if response:
                logger.info(f"Set mode to {mode.name}")
                return True
        return False
    
    def set_flow_rate(self, rate_ul_min: float) -> bool:
        """
        Set flow rate in μL/min
        
        Args:
            rate_ul_min: Flow rate (0.001 - 127000 μL/min)
        """
        if not (0.001 <= rate_ul_min <= 127000):
            logger.error(f"Flow rate {rate_ul_min} out of range (0.001-127000 μL/min)")
            return False
        
        command = f"RATE:{rate_ul_min:.3f}"
        response = self.send_command(command)
        if response:
            logger.info(f"Set flow rate to {rate_ul_min} μL/min")
            return True
        return False
    
    def set_volume(self, volume_ul: float) -> bool:
        """
        Set target volume in μL
        
        Args:
            volume_ul: Target volume in microliters
        """
        command = f"VOL:{volume_ul:.3f}"
        response = self.send_command(command)
        if response:
            logger.info(f"Set volume to {volume_ul} μL")
            return True
        return False
    
    def set_syringe_diameter(self, diameter_mm: float) -> bool:
        """
        Set syringe inner diameter in mm
        
        Args:
            diameter_mm: Inner diameter of syringe in millimeters
        """
        command = f"DIA:{diameter_mm:.3f}"
        response = self.send_command(command)
        if response:
            logger.info(f"Set syringe diameter to {diameter_mm} mm")
            return True
        return False
    
    def start(self) -> bool:
        """Start pump operation"""
        response = self.send_command("START")
        if response:
            logger.info("Pump started")
            return True
        return False
    
    def stop(self) -> bool:
        """Stop pump operation"""
        response = self.send_command("STOP")
        if response:
            logger.info("Pump stopped")
            return True
        return False
    
    def get_status(self) -> Optional[str]:
        """Get pump status"""
        return self.send_command("STATUS")
    
    def modify_flow_rate_online(self, new_rate_ul_min: float) -> bool:
        """
        Modify flow rate while pump is running (online modification)
        
        Args:
            new_rate_ul_min: New flow rate in μL/min
        """
        command = f"RATE_ONLINE:{new_rate_ul_min:.3f}"
        response = self.send_command(command)
        if response:
            logger.info(f"Modified flow rate online to {new_rate_ul_min} μL/min")
            return True
        return False


def demo_automation():
    """
    Demo automation sequence showing all 4 working modes
    """
    # List available serial ports on macOS
    print("\n=== ISPLab02 Syringe Pump Automation Demo ===\n")
    print("Common USB-Serial ports on macOS:")
    print("  - /dev/tty.usbserial")
    print("  - /dev/cu.usbserial")
    print("  - /dev/tty.usbserial-XXXXX")
    print("\nMake sure your USB-to-Serial adapter is connected!")
    
    # Get port from user
    port = input("\nEnter serial port (or press Enter for default /dev/tty.usbserial): ").strip()
    if not port:
        port = '/dev/tty.usbserial'
    
    # Create controller
    pump = ISPLab02Controller(port=port)
    
    # Connect to pump
    if not pump.connect():
        print("Failed to connect to pump. Please check:")
        print("1. USB-to-Serial adapter is connected")
        print("2. Pump is powered on")
        print("3. Serial port name is correct")
        print("\nTo list available ports, run: ls /dev/tty.* | grep -i serial")
        return
    
    try:
        # Initial setup
        print("\n--- Initial Setup ---")
        pump.set_syringe_diameter(14.5)  # Example: 10ml syringe diameter
        pump.set_volume(1000)  # 1000 μL = 1 mL
        pump.set_flow_rate(100)  # 100 μL/min
        
        # Demo Mode 1: INFUSION
        print("\n--- Mode 1: INFUSION ---")
        pump.set_mode(PumpMode.INFUSION)
        pump.start()
        time.sleep(3)
        pump.stop()
        
        # Demo Mode 2: WITHDRAWAL
        print("\n--- Mode 2: WITHDRAWAL ---")
        pump.set_mode(PumpMode.WITHDRAWAL)
        pump.set_flow_rate(150)
        pump.start()
        time.sleep(3)
        pump.stop()
        
        # Demo Mode 3: INFUSION/WITHDRAWAL
        print("\n--- Mode 3: INFUSION/WITHDRAWAL ---")
        pump.set_mode(PumpMode.INFUSION_WITHDRAWAL)
        pump.set_flow_rate(200)
        pump.start()
        time.sleep(2)
        # Demonstrate online flow rate modification
        pump.modify_flow_rate_online(250)
        time.sleep(2)
        pump.stop()
        
        # Demo Mode 4: WITHDRAWAL/INFUSION
        print("\n--- Mode 4: WITHDRAWAL/INFUSION ---")
        pump.set_mode(PumpMode.WITHDRAWAL_INFUSION)
        pump.set_flow_rate(175)
        pump.start()
        time.sleep(3)
        pump.stop()
        
        # Get final status
        print("\n--- Final Status ---")
        status = pump.get_status()
        if status:
            print(f"Pump status: {status}")
        
        print("\n=== Demo Complete ===")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        pump.stop()
    
    finally:
        pump.disconnect()


def custom_sequence():
    """
    Run a custom automation sequence
    """
    print("\n=== Custom Automation Sequence ===\n")
    
    port = input("Enter serial port (default /dev/tty.usbserial): ").strip() or '/dev/tty.usbserial'
    pump = ISPLab02Controller(port=port)
    
    if not pump.connect():
        print("Failed to connect to pump")
        return
    
    try:
        # Get parameters from user
        diameter = float(input("Enter syringe diameter (mm): "))
        pump.set_syringe_diameter(diameter)
        
        print("\nSelect mode:")
        print("1. Infusion")
        print("2. Withdrawal")
        print("3. Infusion/Withdrawal")
        print("4. Withdrawal/Infusion")
        
        mode_choice = int(input("Enter choice (1-4): "))
        modes = [PumpMode.INFUSION, PumpMode.WITHDRAWAL, 
                PumpMode.INFUSION_WITHDRAWAL, PumpMode.WITHDRAWAL_INFUSION]
        pump.set_mode(modes[mode_choice - 1])
        
        volume = float(input("Enter target volume (μL): "))
        pump.set_volume(volume)
        
        rate = float(input("Enter flow rate (μL/min): "))
        pump.set_flow_rate(rate)
        
        input("\nPress Enter to start pump...")
        pump.start()
        
        print("Pump running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping pump...")
        pump.stop()
    
    finally:
        pump.disconnect()


if __name__ == "__main__":
    print("ISPLab02 Syringe Pump Controller")
    print("-" * 35)
    print("1. Run demo automation")
    print("2. Run custom sequence")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '1':
        demo_automation()
    elif choice == '2':
        custom_sequence()
    else:
        print("Exiting...")