import random
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from pymodbus.client import ModbusTcpClient
except Exception:  # pragma: no cover - optional runtime dependency
    ModbusTcpClient = None

from Logic import alarms, motors, ovens, sensors
from modbus_client import readAll


st.set_page_config(page_title="BizMastas Line Monitor", page_icon="🏭", layout="wide")


CSS = """
<style>
    .stApp {
        background: linear-gradient(180deg, #f3f7fb 0%, #edf3f7 100%);
        color: #12304a;
    }
    h1, h2, h3 {
        color: #0d3b66 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.85);
        border: 1px solid rgba(13,59,102,0.10);
        border-left: 5px solid #0d3b66;
        border-radius: 14px;
        box-shadow: 0 6px 20px rgba(17, 35, 52, 0.08);
        padding: 0.5rem 0.75rem;
    }
    .status-ok { color: #1f8f5f; }
    .status-warn { color: #d97706; }
    .status-crit { color: #b42318; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

if "ticks" not in st.session_state:
    st.session_state.ticks = pd.DataFrame()


def make_simulated_raw():
    return {
        "coils": [True, True, True, True, False, False, False, False],
        "discrete": [True, False, True, False, True, False],
        "holding": [
            142.5, 148.2, 146.1, 150.7, 144.4, 147.8,
            145.0, 145.0, 145.0, 145.0, 145.0, 145.0,
            22.5, 22.5, 35.2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ],
        "input_regs": [320, 85, 0, 0, 0, 0],
    }


def fetch_live_or_simulated_data():
    if ModbusTcpClient is None:
        return make_simulated_raw(), False

    client = ModbusTcpClient("192.168.1.88", port=502, timeout=2)
    try:
        connected = client.connect()
        if not connected:
            return make_simulated_raw(), False

        raw = readAll(client)
        if not raw or raw.get("Error"):
            return make_simulated_raw(), False

        raw.setdefault("coils", [False] * 8)
        raw.setdefault("discrete", [True] * 8)
        raw.setdefault("holding", [0] * 30)
        raw.setdefault("input_regs", [0] * 10)
        return raw, True
    except Exception:
        return make_simulated_raw(), False
    finally:
        try:
            client.close()
        except Exception:
            pass


raw, plc_online = fetch_live_or_simulated_data()
oven_data = ovens.process_ovens(raw.get("holding", []))
motor_data = motors.process_motors(raw.get("coils", []), raw.get("holding", []))
sensor_data = sensors.process_sensors(raw.get("discrete", []), raw.get("input_regs", []))
alert_list = alarms.evaluate_alarms(oven_data, motor_data, sensor_data)


st.title("BIASHARA MASTERS SAWMILL")
st.caption(f"PLC: {'LIVE' if plc_online else 'SIMULATION'} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Server 192.168.1.88:502")


primary_status = "RUNNING" if any(oven_data.get(f"oven{i+1}", {}).get("running", False) for i in range(1, 7)) else "IDLE"
status_color = "status-ok" if primary_status == "RUNNING" else "status-warn"

with st.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Line Status", primary_status, delta="Production view")
    c2.metric("Average Oven Temp", f"{oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C", delta=f"Spread {oven_data.get('stats', {}).get('delta_max_min', 0):.1f}°C")
    c3.metric("Line Speed", f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min", delta=f"Setpoint {motor_data.get('main_drive', {}).get('speed_setpoint', 0):.1f}")
    c4.metric("Active Alerts", len(alert_list), delta=f"{len([a for a in alert_list if a.get('level') == 'CRIT'])} critical")


st.subheader("Oven Temperatures")
oven_cols = st.columns(3)
for idx in range(6):
    oven = oven_data[f"oven{idx + 1}"]
    with oven_cols[idx % 3]:
        label = f"Oven {idx + 1} • {oven['status']}"
        st.markdown(f"### {label}")
        st.metric("Actual", f"{oven['actual']:.1f}°C", delta=f"{oven['delta']:+.1f}°C vs setpoint {oven['setpoint']:.1f}°C")
        if oven['setpoint']:
            progress_value = min(max((oven['actual'] / oven['setpoint']) * 100, 0), 100)
            st.progress(progress_value / 100)


new_row = {"time": datetime.now()}
for idx in range(6):
    new_row[f"oven{idx + 1}"] = oven_data[f"oven{idx + 1}"]["actual"]
new_row["line_speed"] = motor_data.get("main_drive", {}).get("speed_actual", 0)

st.session_state.ticks = pd.concat([st.session_state.ticks, pd.DataFrame([new_row])], ignore_index=True).tail(200)

st.subheader("Trend Analysis")
fig = go.Figure()
for idx in range(6):
    fig.add_trace(
        go.Scatter(
            x=st.session_state.ticks["time"],
            y=st.session_state.ticks[f"oven{idx + 1}"],
            mode="lines",
            name=f"Oven {idx + 1}",
            line=dict(width=2),
        )
    )
fig.update_layout(
    template="plotly_white",
    height=420,
    legend_title_text="Line",
    xaxis_title="Time",
    yaxis_title="Temperature (°C)",
    margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig, use_container_width=True)


st.subheader("Equipment Status")
status_cols = st.columns(2)
with status_cols[0]:
    drive = motor_data.get("main_drive", {})
    pump = motor_data.get("hydraulic_pump", {})
    st.markdown("### Drives")
    st.metric("Main Drive", "RUNNING" if drive.get("run", False) else "STOPPED", delta=f"{drive.get('speed_actual', 0):.1f} m/min")
    st.metric("Hydraulic Pump", "RUNNING" if pump.get("run", False) else "STOPPED", delta=f"{pump.get('pressure', 0):.1f} bar")
    st.metric("Unwinder", "RUNNING" if motor_data.get("unwinder", {}).get("run", False) else "STOPPED")
    st.metric("Rewinder", "RUNNING" if motor_data.get("rewinder", {}).get("run", False) else "STOPPED")

with status_cols[1]:
    st.markdown("### Safety & Process")
    st.metric("E-Stop", "OK" if sensor_data.get("e_stop_ok", True) else "TRIPPED")
    st.metric("Resin Level", "OK" if not sensor_data.get("resin_low", False) else "LOW")
    st.metric("Board Sensor", "PRESENT" if sensor_data.get("board_present", False) else "ABSENT")
    st.metric("Line Temperature", f"{sensor_data.get('line_temp', 0):.1f}°C")


st.subheader("Alarm Log")
if alert_list:
    alert_df = pd.DataFrame(alert_list)
    st.dataframe(alert_df, use_container_width=True, hide_index=True)
else:
    st.success("No active alarms. Line is stable and within operating thresholds.")


st.subheader("Operational Summary")
summary_data = {
    "Metric": [
        "Average oven temperature",
        "Spread across ovens",
        "Main drive speed",
        "Hydraulic pressure",
        "Safety status",
    ],
    "Value": [
        f"{oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C",
        f"{oven_data.get('stats', {}).get('delta_max_min', 0):.1f}°C",
        f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min",
        f"{motor_data.get('hydraulic_pump', {}).get('pressure', 0):.1f} bar",
        "Normal" if sensor_data.get("e_stop_ok", True) and not sensor_data.get("resin_low", False) else "Attention",
    ],
}
summary_df = pd.DataFrame(summary_data)
st.dataframe(summary_df, hide_index=True, use_container_width=True)


st.caption("BizMastas © 2026 — Impregnation line monitor")
