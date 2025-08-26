#!/usr/bin/env python3
"""
ISPLab02 Syringe Pump Controller (Drifton)
Automation script using Modbus RTU protocol for ISPLab02 with touch screen
"""

import serial
import time
import struct
from enum import Enum
from typing import Optional, Tuple, List
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


class ModbusRTU:
    """Modbus RTU protocol implementation for ISPLab02"""
    
    @staticmethod
    def calculate_crc16(data: bytes) -> int:
        """Calculate Modbus CRC16"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    @staticmethod
    def build_request(slave_id: int, function_code: int, register_addr: int, 
                     value: int = None, count: int = 1) -> bytes:
        """
        Build Modbus RTU request frame
        
        Args:
            slave_id: Slave device ID (typically 1)
            function_code: Modbus function (3=read, 6=write single, 16=write multiple)
            register_addr: Starting register address
            value: Value to write (for write functions)
            count: Number of registers to read
        """
        if function_code == 3:  # Read holding registers
            data = struct.pack('>BBH H', slave_id, function_code, register_addr, count)
        elif function_code == 6:  # Write single register
            data = struct.pack('>BBH H', slave_id, function_code, register_addr, value)
        elif function_code == 16:  # Write multiple registers
            # For simplicity, assuming single register write
            byte_count = 2
            data = struct.pack('>BBH HBH', slave_id, function_code, register_addr, 
                             1, byte_count, value)
        else:
            raise ValueError(f"Unsupported function code: {function_code}")
        
        crc = ModbusRTU.calculate_crc16(data)
        return data + struct.pack('<H', crc)
    
    @staticmethod
    def parse_response(response: bytes) -> Optional[int]:
        """Parse Modbus RTU response"""
        if len(response) < 5:
            return None
        
        # Check CRC
        received_crc = struct.unpack('<H', response[-2:])[0]
        calculated_crc = ModbusRTU.calculate_crc16(response[:-2])
        
        if received_crc != calculated_crc:
            logger.error("CRC check failed")
            return None
        
        # Extract value based on function code
        function_code = response[1]
        if function_code == 3:  # Read response
            if len(response) >= 7:
                return struct.unpack('>H', response[3:5])[0]
        elif function_code == 6:  # Write single register response
            if len(response) >= 8:
                return struct.unpack('>H', response[4:6])[0]
        
        return None


class ISPLab02ModbusController:
    """Controller class for ISPLab02 Syringe Pump using Modbus RTU"""
    
    # Modbus register addresses (estimated - adjust based on actual documentation)
    REGISTERS = {
        'MODE': 0x0001,           # Working mode register
        'FLOW_RATE': 0x0010,      # Flow rate register
        'VOLUME': 0x0020,         # Volume register
        'SYRINGE_DIA': 0x0030,    # Syringe diameter register
        'START_STOP': 0x0040,     # Start/Stop control register
        'STATUS': 0x0050,         # Status register
        'DIRECTION': 0x0060,      # Direction register
        'LINEAR_SPEED': 0x0070,   # Linear speed register
    }
    
    def __init__(self, port: str = '/dev/tty.usbserial', 
                 baudrate: int = 9600, slave_id: int = 1):
        """
        Initialize pump controller
        
        Args:
            port: Serial port
            baudrate: Communication speed (typically 9600 for Modbus RTU)
            slave_id: Modbus slave ID (default 1)
        """
        self.port = port
        self.baudrate = baudrate
        self.slave_id = slave_id
        self.serial_conn = None
        self.is_connected = False
        
    def connect(self) -> bool:
        """Establish serial connection with pump"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_EVEN,  # Modbus RTU typically uses even parity
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            self.is_connected = True
            logger.info(f"Connected to ISPLab02 on {self.port} (Modbus RTU)")
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
    
    def read_register(self, register_name: str) -> Optional[int]:
        """Read a Modbus register"""
        if not self.is_connected:
            logger.error("Not connected to pump")
            return None
        
        register_addr = self.REGISTERS.get(register_name)
        if not register_addr:
            logger.error(f"Unknown register: {register_name}")
            return None
        
        try:
            # Build read request
            request = ModbusRTU.build_request(self.slave_id, 3, register_addr, count=1)
            
            # Send request
            self.serial_conn.write(request)
            logger.debug(f"Sent Modbus read request for {register_name}")
            
            # Read response
            time.sleep(0.05)
            response = self.serial_conn.read(256)
            
            if response:
                value = ModbusRTU.parse_response(response)
                logger.debug(f"Read {register_name}: {value}")
                return value
                
        except Exception as e:
            logger.error(f"Error reading register: {e}")
        
        return None
    
    def write_register(self, register_name: str, value: int) -> bool:
        """Write to a Modbus register"""
        if not self.is_connected:
            logger.error("Not connected to pump")
            return False
        
        register_addr = self.REGISTERS.get(register_name)
        if not register_addr:
            logger.error(f"Unknown register: {register_name}")
            return False
        
        try:
            # Build write request
            request = ModbusRTU.build_request(self.slave_id, 6, register_addr, value=value)
            
            # Send request
            self.serial_conn.write(request)
            logger.debug(f"Sent Modbus write request for {register_name}: {value}")
            
            # Read response
            time.sleep(0.05)
            response = self.serial_conn.read(256)
            
            if response:
                result = ModbusRTU.parse_response(response)
                if result is not None:
                    logger.info(f"Written {register_name}: {value}")
                    return True
                    
        except Exception as e:
            logger.error(f"Error writing register: {e}")
        
        return False
    
    def set_mode(self, mode: PumpMode) -> bool:
        """Set pump operating mode"""
        mode_values = {
            PumpMode.INFUSION: 1,
            PumpMode.WITHDRAWAL: 2,
            PumpMode.INFUSION_WITHDRAWAL: 3,
            PumpMode.WITHDRAWAL_INFUSION: 4
        }
        
        value = mode_values.get(mode)
        if value:
            success = self.write_register('MODE', value)
            if success:
                logger.info(f"Set mode to {mode.name}")
            return success
        return False
    
    def set_flow_rate(self, rate_ul_min: float) -> bool:
        """
        Set flow rate in μL/min
        Range: 0.002 μL/min - 165.871 mL/min
        """
        if not (0.002 <= rate_ul_min <= 165871):
            logger.error(f"Flow rate {rate_ul_min} out of range (0.002-165871 μL/min)")
            return False
        
        # Convert to register value (may need scaling)
        register_value = int(rate_ul_min * 100)  # Example scaling
        success = self.write_register('FLOW_RATE', register_value)
        if success:
            logger.info(f"Set flow rate to {rate_ul_min} μL/min")
        return success
    
    def set_linear_speed(self, speed_um_min: float) -> bool:
        """
        Set linear speed in μm/min
        Range: 1 μm/min - 132 mm/min (132000 μm/min)
        """
        if not (1 <= speed_um_min <= 132000):
            logger.error(f"Linear speed {speed_um_min} out of range (1-132000 μm/min)")
            return False
        
        register_value = int(speed_um_min)
        success = self.write_register('LINEAR_SPEED', register_value)
        if success:
            logger.info(f"Set linear speed to {speed_um_min} μm/min")
        return success
    
    def start(self) -> bool:
        """Start pump operation"""
        success = self.write_register('START_STOP', 1)
        if success:
            logger.info("Pump started")
        return success
    
    def stop(self) -> bool:
        """Stop pump operation"""
        success = self.write_register('START_STOP', 0)
        if success:
            logger.info("Pump stopped")
        return success
    
    def get_status(self) -> Optional[int]:
        """Get pump status"""
        return self.read_register('STATUS')
    
    def save_to_memory(self, slot: int) -> bool:
        """
        Save current parameters to one of 60 memory slots
        
        Args:
            slot: Memory slot number (1-60)
        """
        if not (1 <= slot <= 60):
            logger.error(f"Invalid memory slot: {slot} (must be 1-60)")
            return False
        
        # This would require specific register/command for memory save
        logger.info(f"Saving to memory slot {slot}")
        # Implementation depends on actual protocol
        return True
    
    def load_from_memory(self, slot: int) -> bool:
        """
        Load parameters from one of 60 memory slots
        
        Args:
            slot: Memory slot number (1-60)
        """
        if not (1 <= slot <= 60):
            logger.error(f"Invalid memory slot: {slot} (must be 1-60)")
            return False
        
        logger.info(f"Loading from memory slot {slot}")
        # Implementation depends on actual protocol
        return True


def demo_automation():
    """
    Demo automation sequence showing all 4 working modes
    """
    print("\n=== ISPLab02 Syringe Pump (Drifton) Automation Demo ===")
    print("Using Modbus RTU Protocol\n")
    
    print("Features:")
    print("- Touch screen control")
    print("- 2 syringe capability")
    print("- Flow rate: 0.002 μL/min - 165.871 mL/min")
    print("- 60 memory slots for saving programs")
    print("- 4 working modes\n")
    
    print("Common USB-Serial ports on macOS:")
    print("  - /dev/tty.usbserial")
    print("  - /dev/cu.usbserial")
    print("  - /dev/tty.usbserial-XXXXX")
    
    # Get port from user
    port = input("\nEnter serial port (or press Enter for default): ").strip()
    if not port:
        port = '/dev/tty.usbserial'
    
    # Get Modbus slave ID
    slave_id = input("Enter Modbus slave ID (default 1): ").strip()
    slave_id = int(slave_id) if slave_id else 1
    
    # Create controller
    pump = ISPLab02ModbusController(port=port, slave_id=slave_id)
    
    # Connect to pump
    if not pump.connect():
        print("\nFailed to connect. Please check:")
        print("1. USB-to-RS232/RS485 adapter is connected")
        print("2. Pump is powered on")
        print("3. Serial port name is correct")
        print("4. Modbus slave ID is correct (check pump settings)")
        print("\nTo list available ports: ls /dev/tty.* | grep -i serial")
        return
    
    try:
        print("\n--- Starting Demo Sequence ---")
        
        # Demo each mode
        modes = [
            (PumpMode.INFUSION, 100, "Infusion at 100 μL/min"),
            (PumpMode.WITHDRAWAL, 150, "Withdrawal at 150 μL/min"),
            (PumpMode.INFUSION_WITHDRAWAL, 200, "Infusion/Withdrawal at 200 μL/min"),
            (PumpMode.WITHDRAWAL_INFUSION, 175, "Withdrawal/Infusion at 175 μL/min")
        ]
        
        for mode, rate, description in modes:
            print(f"\n--- Mode {mode.value}: {mode.name} ---")
            print(f"Description: {description}")
            
            pump.set_mode(mode)
            pump.set_flow_rate(rate)
            pump.start()
            
            print(f"Running for 3 seconds...")
            time.sleep(3)
            
            pump.stop()
            print("Stopped")
            
            # Read status
            status = pump.get_status()
            if status is not None:
                print(f"Status: {status}")
        
        # Demonstrate memory function
        print("\n--- Memory Function Demo ---")
        print("Saving current settings to memory slot 1")
        pump.save_to_memory(1)
        
        print("\n=== Demo Complete ===")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        pump.stop()
    
    finally:
        pump.disconnect()


def custom_sequence():
    """
    Run a custom automation sequence with user parameters
    """
    print("\n=== Custom Automation Sequence ===\n")
    
    port = input("Enter serial port (default /dev/tty.usbserial): ").strip() or '/dev/tty.usbserial'
    slave_id = input("Enter Modbus slave ID (default 1): ").strip()
    slave_id = int(slave_id) if slave_id else 1
    
    pump = ISPLab02ModbusController(port=port, slave_id=slave_id)
    
    if not pump.connect():
        print("Failed to connect to pump")
        return
    
    try:
        print("\nSelect mode:")
        print("1. Infusion")
        print("2. Withdrawal")
        print("3. Infusion/Withdrawal")
        print("4. Withdrawal/Infusion")
        
        mode_choice = int(input("Enter choice (1-4): "))
        modes = [PumpMode.INFUSION, PumpMode.WITHDRAWAL, 
                PumpMode.INFUSION_WITHDRAWAL, PumpMode.WITHDRAWAL_INFUSION]
        pump.set_mode(modes[mode_choice - 1])
        
        print("\nSelect speed control:")
        print("1. Flow rate (μL/min)")
        print("2. Linear speed (μm/min)")
        
        speed_choice = input("Enter choice (1-2): ").strip()
        
        if speed_choice == '1':
            rate = float(input("Enter flow rate (0.002-165871 μL/min): "))
            pump.set_flow_rate(rate)
        else:
            speed = float(input("Enter linear speed (1-132000 μm/min): "))
            pump.set_linear_speed(speed)
        
        # Memory option
        save_memory = input("\nSave to memory slot? (y/n): ").lower()
        if save_memory == 'y':
            slot = int(input("Enter memory slot (1-60): "))
            pump.save_to_memory(slot)
        
        input("\nPress Enter to start pump...")
        pump.start()
        
        print("Pump running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
            status = pump.get_status()
            if status is not None:
                print(f"Status: {status}", end='\r')
            
    except KeyboardInterrupt:
        print("\nStopping pump...")
        pump.stop()
    
    finally:
        pump.disconnect()


if __name__ == "__main__":
    print("ISPLab02 Syringe Pump Controller (Drifton)")
    print("=" * 45)
    print("Touch Screen Model - 2 Syringe Capability")
    print("Modbus RTU Protocol Communication")
    print("-" * 45)
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