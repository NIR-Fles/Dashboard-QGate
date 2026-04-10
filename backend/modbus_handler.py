import logging
import asyncio
import threading
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext

logger = logging.getLogger("modbus_handler")

# Mapping of integer values to trigger names (For use on Modbus Holding Register Address 1)
TRIGGER_VALUES = {
    1: "unit_enter",
    2: "capture_step_1",
    3: "capture_step_2",
    4: "unit_exit"
}

VALID_TRIGGERS = list(TRIGGER_VALUES.values())

class TriggerDataBlock(ModbusSequentialDataBlock):
    """
    Custom Modbus DataBlock that intercepts WRITE commands from the PLC.
    When the PLC writes a value to address 1, it triggers our internal event.
    """
    def __init__(self, address, values, callback):
        super().__init__(address, values)
        self.callback = callback

    def setValues(self, address, values):
        # Call the original method to save the data
        super().setValues(address, values)
        
        # We only care about writing to holding register address 1
        if address == 1 and values:
            val = values[0]
            if val in TRIGGER_VALUES:
                # Trigger the callback
                self.callback(address, val)
                
                # Auto-reset the register value to 0 to acknowledge the command
                # We delay this slightly so PyModbus has time to construct the correct 
                # WriteSingleRegister echo response back to the client (sending back the original value).
                def reset_val():
                    super(TriggerDataBlock, self).setValues(1, [0])
                threading.Timer(0.1, reset_val).start()

class ModbusHandler:
    """
    Unified Modbus Handler.
    - Exposes a 'read_triggers()' method for main.py's control loop.
    - Exposes a 'set_mock_signal()' for the /debug/trigger API (curl commands).
    - Can optionally run an asynchronous ModbusTCP Server in a background thread to listen for a real PLC.
    """
    def __init__(self, mode="MOCK", host="0.0.0.0", port=5020, state_manager=None):
        self.mode = mode
        self.host = host
        self.port = port
        self.state_manager = state_manager
        self.addresses = VALID_TRIGGERS  # Exposed for main.py curl command validation
        
        # Internal state to hold triggered events
        self.lock = threading.Lock()
        self._triggers = {k: False for k in self.addresses}
        
        self.active_clients = 0
        
        # We only start the real Modbus Server in TEST or REAL mode
        # In MOCK mode, we skip starting the server to avoid occupying the port
        if mode in ["TEST", "REAL"]:
            self.start_server_thread()
        else:
            logger.info("Modbus Handler initialized in pure MOCK mode (No Network Server).")

    def _trace_connect(self, connecting: bool):
        """Callback invoked by PyModbus when a client connects or disconnects."""
        with self.lock:
            if connecting:
                self.active_clients += 1
            else:
                self.active_clients = max(0, self.active_clients - 1)
            
            is_connected = self.active_clients > 0
            
        logger.info(f"Modbus client {'connected' if connecting else 'disconnected'}. Active clients: {self.active_clients}")
        
        if self.state_manager:
            self.state_manager.set_plc_connected(is_connected)

    def _on_plc_write(self, address, value):
        """Callback invoked when the PLC (Master) writes to our Holding Registers."""
        logger.info(f"Modbus SERVER received write at address {address} with value {value}")
        
        if address == 1 and value in TRIGGER_VALUES:
            trigger_name = TRIGGER_VALUES[value]
            with self.lock:
                self._triggers[trigger_name] = True
            logger.info(f"PLC Modbus Signal Triggered [Value {value}]: {trigger_name}")

    def start_server_thread(self):
        """Starts the PyModbus Async TCP Server in a separate background thread so it doesn't block FastAPI."""
        logger.info(f"Starting Modbus TCP SERVER on {self.host}:{self.port} (Background Thread)...")
        
        def run_server():
            # Initialize Data Store
            # Address 0 to 9, initialized with 0
            datablock = TriggerDataBlock(0, [0] * 10, self._on_plc_write)
            store = ModbusDeviceContext(
                hr=datablock # Holding Registers
            )
            context = ModbusServerContext(devices=store, single=True)
            
            # Start the TCP server correctly via pymodbus helper
            try:
                StartTcpServer(
                    context=context, 
                    address=(self.host, self.port),
                    trace_connect=self._trace_connect
                )
            except Exception as e:
                logger.error(f"Failed to start Modbus Server: {e}")
                
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

    def set_mock_signal(self, register_name):
        """Used by the /debug/trigger API (curl commands) to securely inject a fake signal."""
        if register_name in self.addresses:
            with self.lock:
                self._triggers[register_name] = True
            logger.info(f"API/Mock Signal Triggered: {register_name}")

    def read_triggers(self):
        """
        Consumed by main.py's control loop. 
        Returns current triggers and resets them immediately (OR logic).
        """
        result = {}
        with self.lock:
            for k, v in self._triggers.items():
                result[k] = v
                self._triggers[k] = False # Auto-reset after read
                
        return result

def get_modbus_handler(mode="MOCK", host="0.0.0.0", port=5020, state_manager=None):
    # We bind to 0.0.0.0 to allow external network connections (e.g. from a real PLC)
    return ModbusHandler(mode=mode, host=host, port=port, state_manager=state_manager)
