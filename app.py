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
        background: linear-gradient(180deg, #f4f8fb 0%, #edf2f7 100%);
        color: #12304a;
    }
    h1, h2, h3, h4 {
        color: #0d3b66 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.7rem;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.92);
        border: 1px solid rgba(13,59,102,0.12);
        border-left: 5px solid #0d3b66;
        border-radius: 14px;
        box-shadow: 0 8px 24px rgba(9, 18, 31, 0.08);
        padding: 0.5rem 0.8rem;
    }
    .alert-banner {
        border-radius: 12px;
        padding: 0.8rem 1rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }
    .alert-crit {
        background: rgba(197, 58, 58, 0.12);
        color: #8c1d18;
        border: 1px solid rgba(197, 58, 58, 0.28);
    }
    .alert-warn {
        background: rgba(216, 146, 30, 0.12);
        color: #9a5c00;
        border: 1px solid rgba(216, 146, 30, 0.28);
    }
    .alert-ok {
        background: rgba(25, 135, 84, 0.12);
        color: #0e6b3d;
        border: 1px solid rgba(25, 135, 84, 0.28);
    }
    .status-box {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid rgba(13,59,102,0.10);
        border-radius: 12px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
    }
    .metric-tag {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        background: #e8eef6;
        color: #12304a;
        margin-bottom: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "ticks" not in st.session_state:
    st.session_state.ticks = pd.DataFrame()
if "operator_notes" not in st.session_state:
    st.session_state.operator_notes = "Production steady. Continue monitoring oven balance and resin delivery."


def make_simulated_raw():
    phase = datetime.now().minute
    oven_base = [
        142.5 + (phase % 6) * 0.8,
        146.2 + ((phase + 2) % 6) * 0.9,
        144.8 + ((phase + 3) % 6) * 0.7,
        150.0 + ((phase + 1) % 5) * 0.8,
        147.5 + ((phase + 4) % 5) * 0.9,
        149.3 + ((phase + 2) % 6) * 0.8,
    ]
    return {
        "coils": [True, True, True, True, False, False, False, False],
        "descrete": [True, False, True, False, True, False],
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

        raw = readAll(client)
        if not raw or "holding" not in raw:
            return make_simulated_raw(), False

        return raw, True
    except Exception:
        return make_simulated_raw(), False
    finally:
        try:
            client.close()
        except Exception:
            pass


def get_shift_label(dt):
    hour = dt.hour
    if 6 <= hour < 14:
        return "Day Shift"
    if 14 <= hour < 22:
        return "Afternoon Shift"
    return "Night Shift"


raw, plc_online = fetch_data()
holding = raw.get("holding", [0] * 30)
coils = raw.get("coils", [False] * 8)
discrete = raw.get("discrete", [True] * 8)
input_regs = raw.get("input_regs", [0] * 10)

oven_data = ovens.process_ovens(holding)
motor_data = motors.process_motors(coils, holding)
sensor_data = sensors.process_sensors(discrete, input_regs)
alert_list = alarms.evaluate_alarms(oven_data, motor_data, sensor_data)

critical_count = sum(1 for a in alert_list if a.get("level") == "CRIT")
warning_count = sum(1 for a in alert_list if a.get("level") == "WARN")

status_text = "RUNNING" if any(oven_data.get(f"oven{i}", {}).get("running", False) for i in range(1, 7)) else "IDLE"

st.title(DASHBOARD_TITLE)
st.caption(f"PLC: {'LIVE' if plc_online else 'SIMULATION'} • {datetime.now().strftime('%A, %d %b %Y • %H:%M:%S')} • {get_shift_label(datetime.now())}")

if alert_list:
    if critical_count:
        st.markdown(f"<div class='alert-banner alert-crit'>CRITICAL ALERTS: {critical_count} active</div>", unsafe_allow_html=True)
    elif warning_count:
        st.markdown(f"<div class='alert-banner alert-warn'>WARNING ALERTS: {warning_count} active</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='alert-banner alert-ok'>SYSTEM HEALTHY: No active alarms</div>", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Plant Status", status_text, delta="Production view")
k2.metric("Average Oven Temp", f"{oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C", delta=f"Spread {oven_data.get('stats', {}).get('delta_max_min', 0):.1f}°C")
k3.metric("Line Speed", f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min", delta=f"Setpoint {motor_data.get('main_drive', {}).get('speed_setpoint', 0):.1f}")
k4.metric("Critical Alerts", critical_count, delta=f"{warning_count} warnings")

st.subheader("Oven & Process Overview")
oven_cols = st.columns(3)
for idx in range(6):
    oven = oven_data[f"oven{idx + 1}"]
    with oven_cols[idx % 3]:
        style = "alert-ok" if oven["status"] == "OK" else "alert-warn" if oven["status"] == "WARNING" else "alert-crit"
        st.markdown(f"<div class='alert-banner {style}'>Oven {idx + 1} • {oven['status']}</div>", unsafe_allow_html=True)
        st.metric("Actual", f"{oven['actual']:.1f}°C", delta=f"{oven['delta']:+.1f}°C vs setpoint {oven['setpoint']:.1f}°C")
        progress = min(max((oven['actual'] / max(oven['setpoint'], 1)) * 100, 0), 100)
        st.progress(progress / 100)

st.subheader("Production Line Status")
left, center, right = st.columns(3)

with left:
    st.markdown("<div class='metric-tag'>DRIVES</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='status-box'>
            <strong>Main Drive:</strong> {'RUNNING' if motor_data.get('main_drive', {}).get('run', False) else 'STOPPED'}<br>
            <strong>Speed:</strong> {motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min<br>
            <strong>Setpoint:</strong> {motor_data.get('main_drive', {}).get('speed_setpoint', 0):.1f} m/min
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class='status-box'>
            <strong>Hydraulic Pump:</strong> {'RUNNING' if motor_data.get('hydraulic_pump', {}).get('run', False) else 'STOPPED'}<br>
            <strong>Pressure:</strong> {motor_data.get('hydraulic_pump', {}).get('pressure', 0):.1f} bar
        </div>
        """,
        unsafe_allow_html=True,
    )

with center:
    st.markdown("<div class='metric-tag'>SAFETY</div>", unsafe_allow_html=True)
    st.metric("E-Stop", "OK" if sensor_data.get("e_stop_ok", True) else "TRIPPED")
    st.metric("Resin Level", "OK" if not sensor_data.get("resin_low", False) else "LOW")
    st.metric("Board Sensor", "PRESENT" if sensor_data.get("board_present", False) else "ABSENT")

with right:
    st.markdown("<div class='metric-tag'>PROCESS</div>", unsafe_allow_html=True)
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
    fig.add_trace(go.Scatter(
        x=st.session_state.ticks["time"],
        y=st.session_state.ticks[f"oven{idx + 1}"],
        mode="lines",
        name=f"Oven {idx + 1}",
        line=dict(width=2),
    ))
fig.update_layout(template="plotly_white", height=420, legend_title_text="Ovens", xaxis_title="Time", yaxis_title="Temperature (°C)")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Alarm Intelligence")
if alert_list:
    alert_df = pd.DataFrame(alert_list)
    alert_df["severity"] = alert_df["level"].map({"CRIT": "Critical", "WARN": "Warning"})
    st.dataframe(alert_df[["severity", "msg"]], use_container_width=True, hide_index=True)
else:
    st.success("No alarms raised. All monitored systems are in stable operating range.")

st.subheader("Operational Summary")
summary_cols = st.columns(4)
summary_cols[0].metric("Avg oven temp", f"{oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C")
summary_cols[1].metric("Oven spread", f"{oven_data.get('stats', {}).get('delta_max_min', 0):.1f}°C")
summary_cols[2].metric("Drive speed", f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min")
summary_cols[3].metric("Maintenance flags", len([a for a in alert_list if a.get("level") == "WARN"]))

st.subheader("Shift Notes")
with st.container():
    st.text_area(
        "Operator log",
        value=st.session_state.operator_notes,
        key="operator_notes",
        height=120,
        help="Enter notes for shift handover, interventions, or process observations.",
    )

report_df = pd.DataFrame([
    {
        "timestamp": datetime.now(),
        "shift": get_shift_label(datetime.now()),
        "avg_oven_temp": oven_data.get("stats", {}).get("avg_temp", 0),
        "line_speed": motor_data.get("main_drive", {}).get("speed_actual", 0),
        "critical_alerts": critical_count,
        "warning_alerts": warning_count,
        "e_stop_ok": sensor_data.get("e_stop_ok", True),
        "resin_low": sensor_data.get("resin_low", False),
    }
])

csv_buffer = io.StringIO()
report_df.to_csv(csv_buffer, index=False)

st.download_button(
    "Download shift report",
    data=csv_buffer.getvalue(),
    file_name=f"bizmastas_shift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    mime="text/csv",
)

st.caption("BizMastas © 2026 — Impregnation line production monitoring dashboard")


# End of file
