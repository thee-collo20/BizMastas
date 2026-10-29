# Central alarms brain


def evaluate_alarms(oven_data, motor_data, sensor_data):
    alerts = []

    for alarm in oven_data.get("alarms", []):
        alerts.append({"level": "WARN" if "WARNING" in alarm else "CRIT", "msg": alarm})

    main_drive = motor_data.get("main_drive", {})
    if not main_drive.get("run", True):
        alerts.append({"level": "CRIT", "msg": "MAIN DRIVE STOPPED"})
        if not main_drive.get("stable", True):
            alerts.append({"level": "WARN", "msg": "LINE SPEED UNSTABLE"})

    if not sensor_data.get("e_stop_ok", True):
        alerts.append({"level": "CRIT", "msg": "E-STOP PRESSED"})
    if sensor_data.get("resin_low", False):
        alerts.append({"level": "WARN", "msg": "RESIN LEVEL LOW"})

    return alerts


def evaluate_alarm(oven_data, motor_data, sensor_data):
    return evaluate_alarms(oven_data, motor_data, sensor_data)
