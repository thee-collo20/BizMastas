"""Central configuration for BizMastas.

Everything site-specific lives here: PLC connection, register map, alarm
thresholds and display settings. The logic modules read their register
addresses from REGISTER_MAP, so if the PLC program changes you only edit
this file.
"""
import os

# --- PLC connection (override with environment variables) -------------------
PLC_CONFIG = {
    "ip": os.getenv("BIZMASTAS_PLC_IP", "192.168.1.88"),
    "port": int(os.getenv("BIZMASTAS_PLC_PORT", "502")),
    "timeout": 2,  # seconds
}

# --- Display ----------------------------------------------------------------
TIMEZONE = "Africa/Nairobi"   # used for timestamps and shift labels
REFRESH_SECONDS = 5           # default auto-refresh interval
TREND_POINTS = 200            # samples kept for the trend chart

# --- How many items to read from each Modbus table (all start at address 0) --
READ_BLOCKS = {
    "coils": 8,
    "discrete": 8,
    "holding": 30,
    "input_regs": 10,
}

# --- Register map (single source of truth, used by logic/*.py) ---------------
REGISTER_MAP = {
    "holding": {
        "oven_actual": [0, 1, 2, 3, 4, 5],        # ovens 1-6, actual temp
        "oven_setpoint": [10, 11, 12, 13, 14, 15],  # ovens 1-6, setpoint
        "line_speed_actual": 20,
        "line_speed_setpoint": 21,
        "hydraulic_pressure": 22,
    },
    "coils": {
        "main_drive": 0,
        "hydraulic_pump": 1,
        "unwinder": 2,
        "rewinder": 3,
    },
    "discrete": {
        "e_stop_ok": 0,
        "resin_low": 1,
    },
    "input_regs": {
        "board_present": 0,
        "line_temp": 1,
    },
}

# --- Alarm thresholds ---------------------------------------------------------
THRESHOLDS = {
    "oven_warn_delta": 2.0,      # °C from setpoint -> WARNING
    "oven_crit_delta": 5.0,      # °C from setpoint -> CRITICAL
    "oven_running_min": 50.0,    # °C above which an oven counts as running
    "speed_tolerance": 0.5,      # m/min between actual and setpoint
}

# --- Values used when a register could not be read ---------------------------
DEFAULTS = {
    "oven_setpoint": 145.0,
    "line_speed_setpoint": 22.0,
    "hydraulic_pressure": 35.2,
}
