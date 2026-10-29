import io
import random
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from pymodbus.client import ModbusTcpClient
except Exception:  # pragma: no cover
    ModbusTcpClient = None

from Logic import alarms, motors, ovens, sensors
from modbus_client import readAll

DASHBOARD_TITLE = "BIASHARA MASTERS SAWMILL"

st.set_page_config(page_title=DASHBOARD_TITLE, page_icon="🏭", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
        color: #e5eefb;
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 1.4rem;
    }
    h1, h2, h3, h4 {
        color: #edf6ff !important;
        font-family: 'Segoe UI', sans-serif;
    }
    .metric-card {
        background: rgba(17, 24, 39, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 0.9rem 1rem;
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.25);
    }
    [data-testid="stMetricValue"] {
        font-size: 1.7rem;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-left: 5px solid #38bdf8;
        border-radius: 14px;
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.25);
        padding: 0.5rem 0.8rem;
    }
    .alarm-critical {
        background: rgba(239, 68, 68, 0.14);
        border: 1px solid rgba(248, 113, 113, 0.4);
        color: #fecaca;
        border-radius: 10px;
        padding: 0.8rem 0.9rem;
        margin-bottom: 0.6rem;
        font-weight: 700;
    }
    .alarm-warning {
        background: rgba(245, 158, 11, 0.14);
        border: 1px solid rgba(251, 191, 36, 0.38);
        color: #fef3c7;
        border-radius: 10px;
        padding: 0.8rem 0.9rem;
        margin-bottom: 0.6rem;
        font-weight: 700;
    }
    .alarm-ok {
        background: rgba(34, 197, 94, 0.14);
        border: 1px solid rgba(74, 222, 128, 0.38);
        color: #dcfce7;
        border-radius: 10px;
        padding: 0.8rem 0.9rem;
        margin-bottom: 0.6rem;
        font-weight: 700;
    }
    .summary-box {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        min-height: 82px;
    }
    .pill {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        background: rgba(59, 130, 246, 0.18);
        color: #bfdbfe;
        margin-bottom: 0.75rem;
    }
    .checklist-item {
        background: rgba(15, 23, 42, 0.75);
        border-left: 4px solid #f59e0b;
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.5rem;
        color: #e2e8f0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "ticks" not in st.session_state:
    st.session_state.ticks = pd.DataFrame()
if "operator_notes" not in st.session_state:
    st.session_state.operator_notes = "Production steady. Keep monitoring oven balance, resin supply, and drive stability."


def get_shift_label(dt):
    hour = dt.hour
    if 6 <= hour < 14:
        return "Day Shift"
    if 14 <= hour < 22:
        return "Afternoon Shift"
    return "Night Shift"


def make_simulated_raw():
    phase = datetime.now().minute
    oven_base = [
        142.0 + (phase % 6) * 0.8,
        147.0 + ((phase + 2) % 6) * 0.8,
        145.0 + ((phase + 3) % 6) * 0.7,
        151.0 + ((phase + 1) % 5) * 0.8,
        148.0 + ((phase + 4) % 4) * 0.9,
        149.5 + ((phase + 2) % 5) * 0.8,
    ]
    return {
        "coils": [True, True, True, True, False, False, False, False],
        "discrete": [True, False, True, False, True, False],
        "holding": [
            *oven_base,
            0, 0, 0, 0,
            145, 145, 145, 145, 145, 145,
            22.5, 22.5, 35.2,
            0, 0, 0, 0, 0, 0, 0, 0, 0,
        ],
        "input_regs": [320, 85, 0, 0, 0, 0],
    }


def fetch_data():
    if ModbusTcpClient is None:
        return make_simulated_raw(), False

    client = ModbusTcpClient("192.168.1.88", port=502, timeout=2)
    try:
        connected = client.connect()
        if not connected:
            return make_simulated_raw(), False

        data = readAll(client)
        if not data or "holding" not in data:
            return make_simulated_raw(), False
        return data, True
    except Exception:
        return make_simulated_raw(), False
    finally:
        try:
            client.close()
        except Exception:
            pass


def build_maintenance_watchlist(oven_data, motor_data, sensor_data):
    items = []
    for idx in range(1, 7):
        oven = oven_data.get(f"oven{idx}", {})
        if oven.get("status") == "CRITICAL":
            items.append(f"Oven {idx} outside thermal band. Inspect heater and RTD calibration.")
        elif oven.get("status") == "WARNING":
            items.append(f"Oven {idx} drifting from target. Review airflow and setpoint tuning.")

    drive = motor_data.get("main_drive", {})
    if not drive.get("run", True):
        items.append("Main drive stopped. Verify motor starter, overloads, and drive alarm history.")
    elif not drive.get("stable", True):
        items.append("Line speed unstable. Check drive tuning and load consistency.")

    pump = motor_data.get("hydraulic_pump", {})
    if not pump.get("run", False):
        items.append("Hydraulic pump offline. Inspect pressure switch and pump control circuit.")

    if not sensor_data.get("e_stop_ok", True):
        items.append("E-stop loop tripped. Verify safety chain and reset procedure.")
    if sensor_data.get("resin_low", False):
        items.append("Resin level low. Refill and inspect feed flow restrictions.")

    return items


def compute_efficiency(oven_data, motor_data, sensor_data, alert_list):
    avg_temp = oven_data.get("stats", {}).get("avg_temp", 0.0)
    temperature_spread = oven_data.get("stats", {}).get("delta_max_min", 0.0)
    drive_running = motor_data.get("main_drive", {}).get("run", False)
    critical_count = sum(1 for alert in alert_list if alert.get("level") == "CRIT")
    warning_count = sum(1 for alert in alert_list if alert.get("level") == "WARN")

    score = 100.0
    score -= min(temperature_spread * 2.5, 20)
    score -= critical_count * 12
    score -= warning_count * 4
    score -= 0 if drive_running else 12
    score -= 0 if sensor_data.get("e_stop_ok", True) else 15
    score -= max(0, (145 - avg_temp) * 0.15)
    return round(max(0.0, min(100.0, score)), 1)


raw, plc_online = fetch_data()
holding = raw.get("holding", [0] * 30)
coils = raw.get("coils", [False] * 8)
discrete = raw.get("discrete", [True] * 8)
input_regs = raw.get("input_regs", [0] * 10)

oven_data = ovens.process_ovens(holding)
motor_data = motors.process_motors(coils, holding)
sensor_data = sensors.process_sensors(discrete, input_regs)
alert_list = alarms.evaluate_alarms(oven_data, motor_data, sensor_data)
maintenance_items = build_maintenance_watchlist(oven_data, motor_data, sensor_data)
operation_efficiency = compute_efficiency(oven_data, motor_data, sensor_data, alert_list)
critical_count = sum(1 for alert in alert_list if alert.get("level") == "CRIT")
warning_count = sum(1 for alert in alert_list if alert.get("level") == "WARN")
line_status = "RUNNING" if any(oven_data.get(f"oven{i}", {}).get("running", False) for i in range(1, 7)) else "IDLE"

st.title(DASHBOARD_TITLE)
st.caption(
    f"{datetime.now().strftime('%A, %d %b %Y • %H:%M:%S')} • PLC: {'LIVE' if plc_online else 'SIMULATION'} • {get_shift_label(datetime.now())}"
)

if alert_list:
    if critical_count:
        st.markdown(f"<div class='alarm-critical'>CRITICAL ALERTS: {critical_count} active</div>", unsafe_allow_html=True)
    elif warning_count:
        st.markdown(f"<div class='alarm-warning'>WARNING ALERTS: {warning_count} active</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='alarm-ok'>SYSTEM HEALTHY: No active alarms</div>", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Plant Status", line_status, delta="Production gate")
k2.metric("Avg Oven Temp", f"{oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C", delta=f"Spread {oven_data.get('stats', {}).get('delta_max_min', 0):.1f}°C")
k3.metric("Line Speed", f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min", delta=f"Setpoint {motor_data.get('main_drive', {}).get('speed_setpoint', 0):.1f}")
k4.metric("Efficiency", f"{operation_efficiency:.1f}%", delta=f"{critical_count} critical / {warning_count} warning")

st.subheader("Executive Summary")
summary1, summary2, summary3, summary4 = st.columns(4)
summary1.markdown(
    "<div class='summary-box'><div class='pill'>OVENS</div><br><strong>Avg temp</strong><br>" + f"{oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C" + "</div>",
    unsafe_allow_html=True,
)
summary2.markdown(
    "<div class='summary-box'><div class='pill'>DRIVES</div><br><strong>Line speed</strong><br>" + f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min" + "</div>",
    unsafe_allow_html=True,
)
summary3.markdown(
    "<div class='summary-box'><div class='pill'>SAFETY</div><br><strong>E-stop</strong><br>" + ("OK" if sensor_data.get("e_stop_ok", True) else "TRIPPED") + "</div>",
    unsafe_allow_html=True,
)
summary4.markdown(
    "<div class='summary-box'><div class='pill'>ALERTS</div><br><strong>Active</strong><br>" + str(len(alert_list)) + " events</div>",
    unsafe_allow_html=True,
)

st.subheader("Oven & Process Overview")
oven_cols = st.columns(3)
for idx in range(6):
    oven = oven_data[f"oven{idx + 1}"]
    with oven_cols[idx % 3]:
        state_class = "alarm-ok" if oven["status"] == "OK" else "alarm-warning" if oven["status"] == "WARNING" else "alarm-critical"
        st.markdown(f"<div class='{state_class}'>Oven {idx + 1} • {oven['status']}</div>", unsafe_allow_html=True)
        st.metric("Actual", f"{oven['actual']:.1f}°C", delta=f"{oven['delta']:+.1f}°C vs setpoint {oven['setpoint']:.1f}°C")
        progress = min(max((oven['actual'] / max(oven['setpoint'], 1)) * 100, 0), 100)
        st.progress(progress / 100)

st.subheader("Production Line Status")
left, center, right = st.columns(3)

with left:
    st.markdown("<div class='pill'>DRIVES</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='summary-box'>
            <strong>Main Drive:</strong> {'RUNNING' if motor_data.get('main_drive', {}).get('run', False) else 'STOPPED'}<br>
            <strong>Speed:</strong> {motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min<br>
            <strong>Setpoint:</strong> {motor_data.get('main_drive', {}).get('speed_setpoint', 0):.1f} m/min
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class='summary-box'>
            <strong>Hydraulic Pump:</strong> {'RUNNING' if motor_data.get('hydraulic_pump', {}).get('run', False) else 'STOPPED'}<br>
            <strong>Pressure:</strong> {motor_data.get('hydraulic_pump', {}).get('pressure', 0):.1f} bar
        </div>
        """,
        unsafe_allow_html=True,
    )

with center:
    st.markdown("<div class='pill'>SAFETY</div>", unsafe_allow_html=True)
    st.metric("E-Stop", "OK" if sensor_data.get("e_stop_ok", True) else "TRIPPED")
    st.metric("Resin Level", "OK" if not sensor_data.get("resin_low", False) else "LOW")
    st.metric("Board Sensor", "PRESENT" if sensor_data.get("board_present", False) else "ABSENT")

with right:
    st.markdown("<div class='pill'>PROCESS</div>", unsafe_allow_html=True)
    st.metric("Line Temp", f"{sensor_data.get('line_temp', 0):.1f}°C")
    st.metric("Unwinder", "RUNNING" if motor_data.get("unwinder", {}).get("run", False) else "STOPPED")
    st.metric("Rewinder", "RUNNING" if motor_data.get("rewinder", {}).get("run", False) else "STOPPED")

new_row = {"time": datetime.now()}
for idx in range(6):
    new_row[f"oven{idx + 1}"] = oven_data[f"oven{idx + 1}"]["actual"]
new_row["line_speed"] = motor_data.get("main_drive", {}).get("speed_actual", 0)
new_row["alarm_count"] = len(alert_list)

st.session_state.ticks = pd.concat([st.session_state.ticks, pd.DataFrame([new_row])], ignore_index=True).tail(200)

st.subheader("Trend Monitoring")
fig = go.Figure()
for idx in range(6):
    fig.add_trace(go.Scatter(x=st.session_state.ticks["time"], y=st.session_state.ticks[f"oven{idx + 1}"], mode="lines", name=f"Oven {idx + 1}"))
fig.update_layout(template="plotly_dark", height=420, legend_title_text="Oven zones", xaxis_title="Time", yaxis_title="Temperature (°C)")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Alarm Intelligence")
if alert_list:
    alert_df = pd.DataFrame(alert_list)
    alert_df["severity"] = alert_df["level"].map({"CRIT": "Critical", "WARN": "Warning"})
    st.dataframe(alert_df[["severity", "msg"]], use_container_width=True, hide_index=True)
else:
    st.success("No active alarms. All monitored systems are stable.")

st.subheader("Maintenance Watchlist")
if maintenance_items:
    for item in maintenance_items:
        st.markdown(f"<div class='checklist-item'>{item}</div>", unsafe_allow_html=True)
else:
    st.success("No maintenance actions required at this time.")

st.subheader("Shift Notes")
with st.container():
    st.text_area(
        "Operator log",
        value=st.session_state.operator_notes,
        key="operator_notes",
        height=120,
        help="Enter shift handover notes, process observations, or equipment actions.",
    )

shift_df = pd.DataFrame([
    {
        "timestamp": datetime.now(),
        "shift": get_shift_label(datetime.now()),
        "avg_oven_temp": oven_data.get("stats", {}).get("avg_temp", 0),
        "line_speed": motor_data.get("main_drive", {}).get("speed_actual", 0),
        "efficiency_pct": operation_efficiency,
        "critical_alerts": critical_count,
        "warning_alerts": warning_count,
        "operator_notes": st.session_state.operator_notes,
    }
])

csv_buffer = io.StringIO()
shift_df.to_csv(csv_buffer, index=False)

export1, export2 = st.columns(2)
with export1:
    st.download_button(
        "Download shift report",
        data=csv_buffer.getvalue(),
        file_name=f"bizmastas_shift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
with export2:
    summary_text = (
        f"BizMastas Shift Summary\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Shift: {get_shift_label(datetime.now())}\n"
        f"Average oven temp: {oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C\n"
        f"Line speed: {motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min\n"
        f"Efficiency: {operation_efficiency:.1f}%\n"
        f"Critical alerts: {critical_count}\n"
        f"Warning alerts: {warning_count}\n"
        f"Operator notes: {st.session_state.operator_notes or 'No notes recorded'}\n"
    )
    st.download_button(
        "Download summary",
        data=summary_text,
        file_name=f"bizmastas_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
    )

st.caption("BizMastas © 2026 — Production control dashboard for impregnation line operations")
