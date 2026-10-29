#Central alarms brain

def evaluate_alarm(oven_data, motor_data, sensor_data):
    alerts=[]

    #oven alarms are already on ovens.py
    alerts.extend([{"level":"WARN" if "WARNING" in a else"CRIT", "msg":a} for a in oven_data.get("alarms", [])])

    #motor alarms
    if not motor_data.get("main_drive",{}).get("run", True):
        alerts.append({"level": "CRIT", "msg":"MAIN DRIVE STOPPED"})
        if not motor_data.get("main_drive", {}).get("stable", True):
            alerts.append({"level": "WARN", "msg":"LINE SPEED UNSTABLE"})

    #sensor alarms
    if not sensor_data.get("e_stop_ok", True):
        alerts.append({"level":"CRIT", "msg":"E-STOP PRESSED"})
    if sensor_data.get("resin_low", False):
        alerts.append({"level": "WARN", "msg":"RESIN LEVEL LOW"})

    return alerts
