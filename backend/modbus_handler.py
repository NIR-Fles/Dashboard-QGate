import logging
import random
import time

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    ModbusTcpClient = None

logger = logging.getLogger("modbus_handler")

# Abstract Base Class
class ModbusHandlerBase:
    def __init__(self, host="127.0.0.1", port=5020):
        self.host = host
        self.port = port
        self.addresses = {
            "unit_enter": 0,
            "unit_exit": 1,
            "capture_step_1": 2,
            "capture_step_2": 3
        }
    
    def connect(self):
        raise NotImplementedError
    
    def read_triggers(self):
        raise NotImplementedError
        
    def set_mock_signal(self, register_name):
        logger.warning("set_mock_signal called on non-mock handler")

# Mock Implementation
class MockModbusHandler(ModbusHandlerBase):
    def __init__(self, host="127.0.0.1", port=5020):
        super().__init__(host, port)
        self._mock_registers = [0, 0, 0, 0]
        self.connected = False

    def connect(self):
        self.connected = True
        logger.info("MOCK Modbus: Connected.")
        return True

    def read_triggers(self):
        result = {
            "unit_enter": False,
            "unit_exit": False,
            "capture_step_1": False,
            "capture_step_2": False
        }
        
        result["unit_enter"] = self._mock_registers[0] > 0
        result["unit_exit"] = self._mock_registers[1] > 0
        result["capture_step_1"] = self._mock_registers[2] > 0
        result["capture_step_2"] = self._mock_registers[3] > 0
        
        # Auto-reset
        for i in range(4):
            self._mock_registers[i] = 0
            
        return result

    def set_mock_signal(self, register_name):
        if register_name in self.addresses:
            idx = self.addresses[register_name]
            self._mock_registers[idx] = 1
            logger.info(f"MOCK Signal Triggered: {register_name}")

# Real Implementation
class RealModbusHandler(ModbusHandlerBase):
    def __init__(self, host="127.0.0.1", port=5020):
        super().__init__(host, port)
        self.client = None
        self.connected = False
        
        if ModbusTcpClient is None:
            logger.error("pymodbus not installed! Real mode will fail.")

    def connect(self):
        if ModbusTcpClient:
            self.client = ModbusTcpClient(self.host, port=self.port)
            self.connected = self.client.connect()
            if self.connected:
                logger.info(f"REAL Modbus: Connected to {self.host}:{self.port}")
            else:
                logger.error(f"REAL Modbus: Failed to connect to {self.host}:{self.port}")
            return self.connected
        return False

    def read_triggers(self):
        if not self.connected:
            self.connect()

        result = {
            "unit_enter": False,
            "unit_exit": False,
            "capture_step_1": False,
            "capture_step_2": False
        }
        
        if not self.connected or not self.client:
            return result
            
        try:
            rr = self.client.read_holding_registers(0, 4)
            if not rr.isError():
                regs = rr.registers
                result["unit_enter"] = regs[0] > 0
                result["unit_exit"] = regs[1] > 0
                result["capture_step_1"] = regs[2] > 0
                result["capture_step_2"] = regs[3] > 0
        except Exception as e:
            logger.error(f"Modbus Read Error: {e}")
            self.connected = False
            
        return result

# Factory Function
def get_modbus_handler(mode="MOCK", host="127.0.0.1", port=5020):
    if mode == "REAL":
        logger.info("Initializing REAL Modbus Handler")
        return RealModbusHandler(host, port)
    else:
        # Mock serves both MOCK and TEST modes for PLC signals
        logger.info(f"Initializing MOCK Modbus Handler (Mode: {mode})")
        return MockModbusHandler(host, port)
