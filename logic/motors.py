"""Drives, pump and line-speed logic (coils + holding registers)."""
from config import DEFAULTS, REGISTER_MAP, THRESHOLDS
from logic import bit, reg


def process_motors(coils, holding_regs):
    coils = coils or []
    holding_regs = holding_regs or []
    c = REGISTER_MAP["coils"]
    h = REGISTER_MAP["holding"]

    main_drive = {
        "run": bit(coils, c["main_drive"], False),
        "speed_actual": reg(holding_regs, h["line_speed_actual"], 0.0),
        "speed_setpoint": reg(holding_regs, h["line_speed_setpoint"], DEFAULTS["line_speed_setpoint"]),
    }
    main_drive["stable"] = (
        abs(main_drive["speed_actual"] - main_drive["speed_setpoint"]) < THRESHOLDS["speed_tolerance"]
    )

    return {
        "main_drive": main_drive,
        "hydraulic_pump": {
            "run": bit(coils, c["hydraulic_pump"], True),
            "pressure": reg(holding_regs, h["hydraulic_pressure"], DEFAULTS["hydraulic_pressure"]),
        },
        "unwinder": {"run": bit(coils, c["unwinder"], True)},
        "rewinder": {"run": bit(coils, c["rewinder"], True)},
    }
