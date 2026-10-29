import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime
import plotly.graph_objects as go

try:
    from pymodbus.client import ModbusTcpClient
    REAL_PLC = True
except Exception:
    REAL_PLC = False

from modbus_client import readAll
from Logic import ovens, motors, sensors, alarms

DASHBOARD_TITLE = "BIASHARA MASTERS SAWMILL"

st.set_page_config(
    page_title=DASHBOARD_TITLE,
    layout="wide"
)

st.markdown("""
<style>
    .stApp{background:#f5f7fa;}
    h1, h2, h3{color:#0d47a1 !important; font-family: monospace;}
    div[data-testid="stMetric"]{background:white; border-radius:12px; border-left:4px solid #0d47a1; box-shadow: 0 2px 8px rgba(0,0,0,0.06);}
</style>""", unsafe_allow_html=True)

if 'ticks' not in st.session_state:
    st.session_state.ticks = pd.DataFrame()

st.title(DASHBOARD_TITLE)
st.caption(f"SERVER 192.168.1.88:502 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EAT | {'LIVE' if REAL_PLC else 'SIMULATION'}")

if REAL_PLC:
    try:
        client = ModbusTcpClient("192.168.1.88", port=502, timeout=2)
        client.connect()
        raw = readAll(client)
        client.close()
        if not raw or "holding" not in raw:
            raise KeyError("holding")
    except Exception:
        REAL_PLC = False
        raw = {
            'coils': [True, True, True, True, False, False, False, False],
            'descrete': [True, False, True, False, True, False],
            'holding': [145, 146, 145, 147, 146, 148, 0, 0, 0, 0, 145, 145, 145, 145, 145, 145, 22.5, 22.5, 35.2] + [0] * 10,
            'input_regs': [320, 85]
        }
else:
    raw = {
        'coils': [True, True, True, True, False, False, False, False],
        'descrete': [random.choice([True, False]), True, True, False],
        'holding': [145 + random.uniform(-2, 2) for _ in range(6)] + [0] * 4 + [22, 22, 35],
        'input_regs': [320, 85]
    }

holding = raw.get('holding', [0] * 30)
coils = raw.get('coils', [False] * 8)
discrete = raw.get('descrete', [True] * 8)
input_regs = raw.get('input_regs', [0] * 10)

oven_data = ovens.process_ovens(holding)
motor_data = motors.process_motors(coils, holding)
sensor_data = sensors.process_sensors(discrete, input_regs)
alert_list = alarms.evaluate_alarms(oven_data, motor_data, sensor_data)

cols = st.columns(3)
for i in range(6):
    o = oven_data[f"oven{i+1}"]
    col = cols[i % 3]
    col.metric(
        f"Oven-{i+1} {o['status']}",
        f"{o['actual']} Celsius",
        f"{o['delta']:+.1f} Celsius vs {o['setpoint']} Celsius"
    )

new_row = {
    "time": datetime.now(),
    **{f"oven{i+1}": oven_data[f"oven{i+1}"]['actual'] for i in range(6)}
}

st.session_state.ticks = pd.concat([st.session_state.ticks, pd.DataFrame([new_row])], ignore_index=True)
if len(st.session_state.ticks) > 200:
    st.session_state.ticks = st.session_state.ticks.tail(200)

fig = go.Figure()
colors = ["#0d47a1", "#1976d2", "#ef6c00", "#6a1b9a", "#c62828", "#f9a825"]

for i in range(6):
    fig.add_trace(go.Scatter(
        x=st.session_state.ticks["time"],
        y=st.session_state.ticks[f"oven{i+1}"],
        name=f"OVEN-{i+1}",
        line=dict(color=colors[i % len(colors)])
    ))

fig.update_layout(title=DASHBOARD_TITLE, xaxis_title="Time", yaxis_title="Temperature (°C)")
st.plotly_chart(fig, use_container_width=True)

if alert_list:
    st.subheader("Alarms")
    for alert in alert_list:
        level = alert.get("level", "WARN")
        label = "CRITICAL" if level == "CRIT" else "WARNING"
        st.warning(f"{label}: {alert.get('msg', 'No message')}")
