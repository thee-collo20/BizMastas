"""Central alarm evaluation. Each alert is {"level": "CRIT"|"WARN", "msg": str}."""

_ORDER = {"CRIT": 0, "WARN": 1}


def evaluate_alarms(oven_data, motor_data, sensor_data):
    alerts = list(oven_data.get("alarms", []))

    drive = motor_data.get("main_drive", {})
    if not drive.get("run", True):
        alerts.append({"level": "CRIT", "msg": "MAIN DRIVE STOPPED"})
    elif not drive.get("stable", True):
        alerts.append({"level": "WARN", "msg": "LINE SPEED UNSTABLE"})

    if not sensor_data.get("e_stop_ok", True):
        alerts.append({"level": "CRIT", "msg": "E-STOP PRESSED"})
    if sensor_data.get("resin_low", False):
        alerts.append({"level": "WARN", "msg": "RESIN LEVEL LOW"})

    return sorted(alerts, key=lambda a: _ORDER.get(a["level"], 9))


# Backwards-compatible alias
evaluate_alarm = evaluate_alarms
