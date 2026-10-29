"""Oven logic for the six ovens on the impregnation line.

Actual temperatures and setpoints are read from the holding registers listed
in config.REGISTER_MAP["holding"].
"""
from config import DEFAULTS, REGISTER_MAP, THRESHOLDS
from logic import reg


def process_ovens(holding_regs):
    result = {}
    alarms = []
    holding_regs = holding_regs or []

    actual_idx = REGISTER_MAP["holding"]["oven_actual"]
    setpoint_idx = REGISTER_MAP["holding"]["oven_setpoint"]

    for n, (a_idx, s_idx) in enumerate(zip(actual_idx, setpoint_idx), start=1):
        actual = reg(holding_regs, a_idx, 0.0)
        setpoint = reg(holding_regs, s_idx, DEFAULTS["oven_setpoint"])
        delta = actual - setpoint

        status = "OK"
        if abs(delta) > THRESHOLDS["oven_crit_delta"]:
            status = "CRITICAL"
            alarms.append({"level": "CRIT", "msg": f"OVEN-{n} {delta:+.1f}°C OFF TARGET"})
        elif abs(delta) > THRESHOLDS["oven_warn_delta"]:
            status = "WARNING"
            alarms.append({"level": "WARN", "msg": f"OVEN-{n} {delta:+.1f}°C DRIFTING"})

        result[f"oven{n}"] = {
            "actual": round(actual, 1),
            "setpoint": round(setpoint, 1),
            "delta": round(delta, 1),
            "status": status,
            "running": actual > THRESHOLDS["oven_running_min"],
        }

    actuals = [result[f"oven{n}"]["actual"] for n in range(1, len(actual_idx) + 1)]
    spread = max(actuals) - min(actuals)
    result["stats"] = {
        "avg_temp": round(sum(actuals) / len(actuals), 1),
        "delta_max_min": round(spread, 1),
        "stability": round(100 - spread / 2, 1),
    }
    result["alarms"] = alarms
    return result
