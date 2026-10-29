# This Logic is for the 6 ovens present in the impregnation line.
# reads holding registers 0-11 (0-5 actual, 10-15 set-point)
# pulled after modbus_client reads holding regs.


def process_ovens(holding_regs):
    result = {}
    alarms = []

    actual_index = [0, 1, 2, 3, 4, 5]
    setpoint_index = [10, 11, 12, 13, 14, 15]

    if holding_regs is None:
        holding_regs = []

    for i in range(6):
        try:
            actual = float(holding_regs[actual_index[i]])
        except (IndexError, TypeError, ValueError):
            actual = 0.0

        try:
            setpoint = float(holding_regs[setpoint_index[i]])
        except (IndexError, TypeError, ValueError):
            setpoint = 145.0

        delta = actual - setpoint
        status = "OK"

        if abs(delta) > 5:
            status = "CRITICAL"
            alarms.append(f"OVEN-{i + 1} {delta:+.1f}°C OFF TARGET")
        elif abs(delta) > 2:
            status = "WARNING"

        result[f"oven{i + 1}"] = {
            "actual": round(actual, 1),
            "setpoint": round(setpoint, 1),
            "delta": round(delta, 1),
            "status": status,
            "running": actual > 50,
        }

    actuals = [result[f"oven{i + 1}"]["actual"] for i in range(1, 7)]
    result["stats"] = {
        "avg_temp": round(sum(actuals) / 6, 1) if actuals else 0.0,
        "delta_max_min": round(max(actuals) - min(actuals), 1) if actuals else 0.0,
        "stability": round(100 - ((max(actuals) - min(actuals)) / 2), 1) if actuals else 100.0,
    }
    result["alarms"] = alarms
    return result
