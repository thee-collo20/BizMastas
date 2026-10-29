# Motors / Drives / Line speed logic
# Coils 0-7 + holding 20-22


def process_motors(coils, holding_regs):
    result = {}

    if coils is None:
        coils = []
    if holding_regs is None:
        holding_regs = []

    try:
        result["main_drive"] = {
            "run": bool(coils[0]) if len(coils) > 0 else False,
            "speed_actual": float(holding_regs[20]) if len(holding_regs) > 20 else 0.0,
            "speed_setpoint": float(holding_regs[21]) if len(holding_regs) > 21 else 22.0,
        }

        result["hydraulic_pump"] = {
            "run": bool(coils[1]) if len(coils) > 1 else True,
            "pressure": float(holding_regs[22]) if len(holding_regs) > 22 else 35.2,
        }

        result["unwinder"] = {"run": bool(coils[2]) if len(coils) > 2 else True}
        result["rewinder"] = {"run": bool(coils[3]) if len(coils) > 3 else True}

        delta = abs(result["main_drive"]["speed_actual"] - result["main_drive"]["speed_setpoint"])
        result["main_drive"]["stable"] = delta < 0.5
    except Exception as exc:
        result["error"] = str(exc)

    return result
