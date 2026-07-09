import logging
import asyncio
import threading
import time
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

class SensorCoilDataBlock(ModbusSequentialDataBlock):
    """
    Custom Modbus DataBlock that intercepts WRITE commands to Coils from Factory I/O.
    Simulates proximity sensors combinations into system triggers.
    """
    def __init__(self, address, values, trigger_callback):
        super().__init__(address, values)
        self.trigger_callback = trigger_callback
        
        # Keep track of previous state to detect edges
        # Assuming Sensor 1 -> Coil 1, Sensor 2 -> Coil 2, Sensor 3 -> Coil 3
        # In a 0-based block starting at 0, they are at index 1, 2, 3
        self.prev_state = (False, False, False)
        self.last_trigger = 0 # To prevent double readings (bouncing)

    def setValues(self, address, values):
        super().setValues(address, values)
        
        try:
            curr_s1 = bool(self.values[1])
            curr_s2 = bool(self.values[2])
            curr_s3 = bool(self.values[3])
            curr_state = (curr_s1, curr_s2, curr_s3)
            
            # Detect Sensor 3 falling edge (ON -> OFF) for Factory I/O Sequence Reset (Coil 4)
            prev_s3 = self.prev_state[2]
            if prev_s3 and not curr_s3:
                logger.info("Factory I/O Auto-Reset: Sensor 3 OFF -> Pulsing Coil 4 ON")
                self.values[4] = True # Turn Coil 4 ON
                
                # Thread to turn Coil 4 OFF after a short pulse (e.g. 1 second)
                def reset_coil_4():
                    self.values[4] = False
                    logger.info("Factory I/O Auto-Reset: Coil 4 OFF")
                
                import threading
                threading.Timer(1.0, reset_coil_4).start()
            
            if curr_state != self.prev_state:
                self.prev_state = curr_state
                
                # Apply combination logic
                trigger_val = None
                if curr_state == (True, False, False):
                    trigger_val = 1 # unit_enter
                elif curr_state == (True, True, False):
                    trigger_val = 2 # capture_step_1
                elif curr_state == (False, True, True):
                    trigger_val = 3 # capture_step_2
                elif curr_state == (False, False, True):
                    trigger_val = 4 # unit_exit
                elif curr_state == (False, False, False):
                    trigger_val = 0 # Reset sequence when all sensors are OFF
                
                # Teruskan ke global handler, validasi sequence akan dilakukan di _on_plc_write
                if trigger_val is not None:
                    self.trigger_callback(1, trigger_val)
        except IndexError:
            pass

class TriggerDataBlock(ModbusSequentialDataBlock):
    """
    Custom Modbus DataBlock that intercepts WRITE commands from the PLC.
    When the PLC writes a value to address 1, it triggers our internal event.
    """
    def __init__(self, address, values, callback):
        super().__init__(address, values)
        self.callback = callback
        self.last_val = 0  # Track last written value to prevent duplicate/spam triggers

    def setValues(self, address, values):
        # Call the original method to save the data
        super().setValues(address, values)
        
        # We only care about writing to holding register address 1
        if address == 1 and values:
            val = values[0]
            if val in TRIGGER_VALUES or val == 0:
                # Prevent spam by ignoring consecutive writes of the same value
                if val == self.last_val:
                    return
                
                self.last_val = val
                
                # Trigger the callback
                self.callback(address, val)
                
                # Auto-reset the register value to 0 to acknowledge the command
                # We only auto-reset triggers 1, 2, and 3.
                # For 4 (unit_exit), we let it stay 4 until the PLC/ModbusPoll writes 0 to trigger the falling edge.
                if val in [1, 2, 3]:
                    def reset_val():
                        super(TriggerDataBlock, self).setValues(1, [0])
                        self.last_val = 0
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
        self.datablock = None  # Will be set once the server starts, used for writing back to PLC
        self.last_valid_trigger = 0 # Global tracker untuk Anti-Bouncing & Sequence
        
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
        """Callback invoked when the PLC (Master) writes to our Holding Registers or Coils."""
        logger.info(f"Modbus SERVER received write at address {address} with value {value}")
        
        if address == 1:
            with self.lock:
                if value == 0:
                    if self.last_valid_trigger == 4:
                        self._triggers["unit_exit"] = True
                        logger.info("PLC Modbus Signal Triggered [DIFFERENTIAL DOWN 4->0]: unit_exit")
                    self.last_valid_trigger = 0
                    logger.info("Sequence Reset (0) diterima.")
                    return
                
                if value in TRIGGER_VALUES:
                    # --- Global Strict Sequence & Anti-Bouncing ---
                    is_valid = False
                    if value == 1:
                        is_valid = True # Selalu izinkan Trigger 1 (Boks baru masuk)
                    elif value == self.last_valid_trigger + 1:
                        is_valid = True # Harus berurutan 1->2, 2->3, 3->4
                        
                    if is_valid and value != self.last_valid_trigger:
                        trigger_name = TRIGGER_VALUES[value]
                        if value == 4:
                            self.last_valid_trigger = 4
                            logger.info("PLC Modbus Signal [Value 4] received. WAITING for 0 (Differential Down) to execute unit_exit.")
                        else:
                            self._triggers[trigger_name] = True
                            self.last_valid_trigger = value
                            logger.info(f"PLC Modbus Signal Triggered [Value {value}]: {trigger_name}")
                    else:
                        if value != self.last_valid_trigger:
                            logger.warning(f"Global Modbus: Sequence terabaikan! Boks melompat dari step {self.last_valid_trigger} ke {value}.")

    def start_server_thread(self):
        """Starts the PyModbus Async TCP Server in a separate background thread so it doesn't block FastAPI."""
        logger.info(f"Starting Modbus TCP SERVER on {self.host}:{self.port} (Background Thread)...")
        
        def run_server():
            # Initialize Data Store
            # Address 0 to 9, initialized with 0 for HR, False for Coils
            self.datablock = TriggerDataBlock(0, [0] * 10, self._on_plc_write)
            self.coil_datablock = SensorCoilDataBlock(0, [False] * 10, self._on_plc_write)
            
            store = ModbusDeviceContext(
                co=self.coil_datablock, # Coils for Factory I/O Sensors
                hr=self.datablock       # Holding Registers for PLC triggers and alarms
            )
            context = ModbusServerContext(devices=store, single=True)
            
            # --- PLC Heartbeat ---
            # Writes an incrementing counter (0-100) to Register 4 every 1000ms
            def heartbeat_loop():
                counter = 0
                while True:
                    if self.datablock:
                        try:
                            self.datablock.setValues(4, [counter])
                            counter += 1
                            if counter > 100:
                                counter = 0
                        except Exception as e:
                            logger.error(f"Heartbeat error: {e}")
                    time.sleep(1.0)
            
            threading.Thread(target=heartbeat_loop, daemon=True).start()
            
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

    def send_ng_alarm(self):
        """
        Called by main.py when a unit inspection result is NG.
        Writes 1 to Modbus Holding Register 2 (PLC Alarm Register),
        then auto-resets it back to 0 after 5 seconds.
        """
        if self.datablock is None:
            logger.warning("NG Alarm: Modbus server not started, cannot write to register 2.")
            return

        logger.warning("NG ALARM: Writing 1 to Modbus Register 2 (PLC Alarm Signal).")
        self.datablock.setValues(2, [1])  # Write 1 → register 2

        def reset_alarm():
            self.datablock.setValues(2, [0])  # Reset → 0 after 5 seconds
            logger.info("NG Alarm: Register 2 reset to 0.")

        threading.Timer(5.0, reset_alarm).start()

def get_modbus_handler(mode="MOCK", host="0.0.0.0", port=5020, state_manager=None):
    # We bind to 0.0.0.0 to allow external network connections (e.g. from a real PLC)
    return ModbusHandler(mode=mode, host=host, port=port, state_manager=state_manager)
