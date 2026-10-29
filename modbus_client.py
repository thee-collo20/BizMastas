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


st.set_page_config(page_title="BizMastas Line Monitor", page_icon="🏭", layout="wide")


CSS = """
<style>
    .stApp {
        background: linear-gradient(180deg, #eff6fb 0%, #eef2f7 100%);
        color: #12324a;
    }
    h1, h2, h3, h4 {
        color: #0d3b66 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.55rem;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.9);
        border: 1px solid rgba(13,59,102,0.12);
        border-left: 5px solid #0d3b66;
        border-radius: 14px;
        box-shadow: 0 8px 24px rgba(9, 18, 31, 0.08);
        padding: 0.5rem 0.75rem;
    }
    .alert-banner {
        border-radius: 12px;
        padding: 0.8rem 1rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
    }
    .alert-crit {
        background: rgba(197, 58, 58, 0.12);
        color: #8c1d18;
        border: 1px solid rgba(197, 58, 58, 0.26);
    }
    .alert-warn {
        background: rgba(216, 146, 30, 0.12);
        color: #9a5c00;
        border: 1px solid rgba(216, 146, 30, 0.26);
    }
    .alert-ok {
        background: rgba(25, 135, 84, 0.12);
        color: #0e6b3d;
        border: 1px solid rgba(25, 135, 84, 0.26);
    }
    .maintenance-item {
        background: linear-gradient(180deg, #fff9f2 0%, #fff 100%);
        border-left: 5px solid #f59e0b;
        padding: 0.7rem 0.9rem;
        border-radius: 10px;
        margin-bottom: 0.5rem;
    }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


if "ticks" not in st.session_state:
    st.session_state.ticks = pd.DataFrame()


def get_shift_label(dt):
    hour = dt.hour
    if 6 <= hour < 14:
        return "Day Shift"
    if 14 <= hour < 22:
        return "Afternoon Shift"
    return "Night Shift"


def make_simulated_raw():
    phase = datetime.now().minute
    oven_base = [144 + (phase % 7) * 0.8, 148.5, 145.2, 151.4, 147.2, 149.1]
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


def fetch_live_or_simulated_data():
    if ModbusTcpClient is None:
        return make_simulated_raw(), False

    client = ModbusTcpClient("192.168.1.88", port=502, timeout=2)
    try:
        connected = client.connect()
        if not connected:
            return make_simulated_raw(), False

        try:
            from modbus_client import readAll
            raw = readAll(client)
        except Exception:
            raw = {}

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


def build_maintenance_items(oven_data, motor_data, sensor_data):
    items = []

    for idx in range(1, 7):
        oven = oven_data.get(f"oven{idx}", {})
        if oven.get("status") == "CRITICAL":
            items.append(f"Oven {idx} operating outside thermal band — inspect heaters and RTD sensor.")
        elif oven.get("status") == "WARNING":
            items.append(f"Oven {idx} drifting from setpoint — check calibration and airflow.")

    drive = motor_data.get("main_drive", {})
    if not drive.get("run", True):
        items.append("Main drive is stopped — verify motor starter, overloads, and drive faults.")
    elif not drive.get("stable", True):
        items.append("Line speed variation detected — inspect drive tuning and load consistency.")

    pump = motor_data.get("hydraulic_pump", {})
    if not pump.get("run", False):
        items.append("Hydraulic pump not running — inspect pressure switch and pump control circuit.")

    if not sensor_data.get("e_stop_ok", True):
        items.append("E-stop chain tripped — verify safety loop and reset the interlock.")

    if sensor_data.get("resin_low", False):
        items.append("Resin level low — refill and check feed system for blockage.")

    return items


def build_shift_summary(df):
    if df.empty:
        return {"avg_temp": 0.0, "peak_temp": 0.0, "line_speed": 0.0, "alert_count": 0}

    temp_cols = [c for c in df.columns if c.startswith("oven")]
    avg_temp = float(df[temp_cols].mean().mean()) if temp_cols else 0.0
    peak_temp = float(df[temp_cols].max().max()) if temp_cols else 0.0
    line_speed = float(df["line_speed"].mean()) if "line_speed" in df.columns else 0.0
    alert_count = int(len(df[df["alarm_count"] > 0])) if "alarm_count" in df.columns else 0
    return {
        "avg_temp": avg_temp,
        "peak_temp": peak_temp,
        "line_speed": line_speed,
        "alert_count": alert_count,
    }


raw, plc_online = fetch_live_or_simulated_data()
oven_data = ovens.process_ovens(raw.get("holding", []))
motor_data = motors.process_motors(raw.get("coils", []), raw.get("holding", []))
sensor_data = sensors.process_sensors(raw.get("discrete", []), raw.get("input_regs", []))
alert_list = alarms.evaluate_alarms(oven_data, motor_data, sensor_data)
maintenance_items = build_maintenance_items(oven_data, motor_data, sensor_data)


st.title("BizMastas • Impregnation Line Dashboard")
st.caption(f"{datetime.now().strftime('%A, %d %b %Y • %H:%M:%S')} • PLC: {'LIVE' if plc_online else 'SIMULATION'} • {get_shift_label(datetime.now())}")

if alert_list:
    critical_count = sum(1 for a in alert_list if a.get("level") == "CRIT")
    warning_count = sum(1 for a in alert_list if a.get("level") == "WARN")

    if critical_count:
        st.markdown(f"<div class='alert-banner alert-crit'>CRITICAL ALERTS: {critical_count} active</div>", unsafe_allow_html=True)
    elif warning_count:
        st.markdown(f"<div class='alert-banner alert-warn'>WARNING ALERTS: {warning_count} active</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='alert-banner alert-ok'>SYSTEM HEALTHY: No active alarms</div>", unsafe_allow_html=True)


with st.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plant Status", "Running" if any(oven_data.get(f"oven{i}", {}).get("running", False) for i in range(1, 7)) else "Idle", delta="Production gate")
    c2.metric("Average Oven Temp", f"{oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C", delta=f"Spread {oven_data.get('stats', {}).get('delta_max_min', 0):.1f}°C")
    c3.metric("Line Speed", f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min", delta=f"Setpoint {motor_data.get('main_drive', {}).get('speed_setpoint', 0):.1f}")
    c4.metric("Critical Alerts", sum(1 for a in alert_list if a.get("level") == "CRIT"), delta=f"{len(alert_list)} total alerts")


st.subheader("Oven Performance")
oven_cols = st.columns(3)
for idx in range(6):
    oven = oven_data[f"oven{idx + 1}"]
    with oven_cols[idx % 3]:
        status_class = "alert-ok" if oven["status"] == "OK" else "alert-warn" if oven["status"] == "WARNING" else "alert-crit"
        st.markdown(f"<div class='alert-banner {status_class}'>Oven {idx + 1} • {oven['status']}</div>", unsafe_allow_html=True)
        st.metric("Actual", f"{oven['actual']:.1f}°C", delta=f"{oven['delta']:+.1f}°C vs setpoint {oven['setpoint']:.1f}°C")
        st.progress(min(max((oven['actual'] / max(oven['setpoint'], 1)) * 100, 0), 100) / 100)


new_row = {"time": datetime.now()}
for idx in range(6):
    new_row[f"oven{idx + 1}"] = oven_data[f"oven{idx + 1}"]["actual"]
new_row["line_speed"] = motor_data.get("main_drive", {}).get("speed_actual", 0)
new_row["alarm_count"] = len(alert_list)

st.session_state.ticks = pd.concat([st.session_state.ticks, pd.DataFrame([new_row])], ignore_index=True).tail(200)

st.subheader("Temperature Trend")
fig = go.Figure()
for idx in range(6):
    fig.add_trace(go.Scatter(x=st.session_state.ticks["time"], y=st.session_state.ticks[f"oven{idx + 1}"], mode="lines", name=f"Oven {idx + 1}"))
fig.update_layout(template="plotly_white", height=420, legend_title_text="Zones", xaxis_title="Time", yaxis_title="Temperature (°C)")
st.plotly_chart(fig, use_container_width=True)


left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Equipment Status")
    st.metric("Main Drive", "RUNNING" if motor_data.get("main_drive", {}).get("run", False) else "STOPPED", delta=f"{motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min")
    st.metric("Hydraulic Pump", "RUNNING" if motor_data.get("hydraulic_pump", {}).get("run", False) else "STOPPED", delta=f"{motor_data.get('hydraulic_pump', {}).get('pressure', 0):.1f} bar")
    st.metric("Unwinder", "RUNNING" if motor_data.get("unwinder", {}).get("run", False) else "STOPPED")
    st.metric("Rewinder", "RUNNING" if motor_data.get("rewinder", {}).get("run", False) else "STOPPED")

with right_col:
    st.subheader("Safety & Process")
    st.metric("E-Stop", "OK" if sensor_data.get("e_stop_ok", True) else "TRIPPED")
    st.metric("Resin Level", "OK" if not sensor_data.get("resin_low", False) else "LOW")
    st.metric("Board Sensor", "PRESENT" if sensor_data.get("board_present", False) else "ABSENT")
    st.metric("Line Temperature", f"{sensor_data.get('line_temp', 0):.1f}°C")


st.subheader("Shift Summary")
shift_data = build_shift_summary(st.session_state.ticks)
shift_cols = st.columns(4)
shift_cols[0].metric("Avg oven temp", f"{shift_data['avg_temp']:.1f}°C")
shift_cols[1].metric("Peak temp", f"{shift_data['peak_temp']:.1f}°C")
shift_cols[2].metric("Average line speed", f"{shift_data['line_speed']:.1f} m/min")
shift_cols[3].metric("Shift alarms", str(shift_data['alert_count']))


st.subheader("Maintenance Watchlist")
if maintenance_items:
    for item in maintenance_items:
        st.markdown(f"<div class='maintenance-item'>{item}</div>", unsafe_allow_html=True)
else:
    st.success("No maintenance actions required at this time.")


st.subheader("Alarm Log")
if alert_list:
    alert_df = pd.DataFrame(alert_list)
    alert_df["severity"] = alert_df["level"].map({"CRIT": "Critical", "WARN": "Warning"})
    style_map = {
        "Critical": "background-color: #fdecec; color: #8c1d18; font-weight: 600;",
        "Warning": "background-color: #fff4e5; color: #9a5c00; font-weight: 600;",
    }
    st.dataframe(alert_df[["severity", "msg"]], use_container_width=True, hide_index=True)
else:
    st.success("No active alarms. Line is stable and within operating thresholds.")


st.subheader("Export & Reporting")
report_df = pd.DataFrame({
    "timestamp": [datetime.now()],
    "shift": [get_shift_label(datetime.now())],
    "avg_oven_temp": [oven_data.get("stats", {}).get("avg_temp", 0)],
    "spread": [oven_data.get("stats", {}).get("delta_max_min", 0)],
    "line_speed": [motor_data.get("main_drive", {}).get("speed_actual", 0)],
    "critical_alerts": [sum(1 for a in alert_list if a.get("level") == "CRIT")],
    "warning_alerts": [sum(1 for a in alert_list if a.get("level") == "WARN")],
    "status": ["Normal" if not alert_list else "Attention"],
})

csv_buffer = io.StringIO()
report_df.to_csv(csv_buffer, index=False)

col_export_1, col_export_2 = st.columns(2)
with col_export_1:
    st.download_button(
        label="Download Shift CSV",
        data=csv_buffer.getvalue(),
        file_name=f"bizmastas_shift_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
with col_export_2:
    summary_text = (
        f"BizMastas Shift Report\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Shift: {get_shift_label(datetime.now())}\n"
        f"Average oven temperature: {oven_data.get('stats', {}).get('avg_temp', 0):.1f}°C\n"
        f"Line speed: {motor_data.get('main_drive', {}).get('speed_actual', 0):.1f} m/min\n"
        f"Critical alerts: {sum(1 for a in alert_list if a.get('level') == 'CRIT')}\n"
        f"Warning alerts: {sum(1 for a in alert_list if a.get('level') == 'WARN')}\n"
        f"Maintenance watchlist: {len(maintenance_items)} items\n"
    )
    st.download_button(
        label="Download Summary Report",
        data=summary_text,
        file_name=f"bizmastas_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
    )


st.caption("BizMastas © 2026 — Industrial monitoring for impregnation line operations")
