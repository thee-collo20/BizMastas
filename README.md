import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import PLC_CONFIG, REFRESH_SECONDS, TIMEZONE, TREND_POINTS
from logic import alarms, motors, ovens, sensors
from modbus_client import FactoryPLC, simulate_raw

DASHBOARD_TITLE = "BIASHARA MASTERS SAWMILL"

st.set_page_config(page_title=DASHBOARD_TITLE, page_icon="🏭", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #f4f8fb 0%, #edf2f7 100%); color: #12304a; }
    h1, h2, h3, h4 { color: #0d3b66 !important; font-family: 'Segoe UI', sans-serif; }
    [data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 700; }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.92); border: 1px solid rgba(13,59,102,0.12);
        border-left: 5px solid #0d3b66; border-radius: 14px;
        box-shadow: 0 8px 24px rgba(9, 18, 31, 0.08); padding: 0.5rem 0.8rem;
    }
    .alert-banner { border-radius: 12px; padding: 0.8rem 1rem; font-weight: 600; margin-bottom: 0.75rem; }
    .alert-crit { background: rgba(197,58,58,0.12); color: #8c1d18; border: 1px solid rgba(197,58,58,0.28); }
    .alert-warn { background: rgba(216,146,30,0.12); color: #9a5c00; border: 1px solid rgba(216,146,30,0.28); }
    .alert-ok   { background: rgba(25,135,84,0.12);  color: #0e6b3d; border: 1px solid rgba(25,135,84,0.28); }
    .status-box {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid rgba(13,59,102,0.10); border-radius: 12px;
        padding: 0.8rem 1rem; margin-bottom: 0.6rem;
    }
    .metric-tag {
        display: inline-block; padding: 0.2rem 0.5rem; border-radius: 999px; font-size: 0.72rem;
        font-weight: 700; letter-spacing: 0.04em; background: #e8eef6; color: #12304a; margin-bottom: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- session state
if "ticks" not in st.session_state:
    st.session_state.ticks = pd.DataFrame()
if "operator_notes" not in st.session_state:
    st.session_state.operator_notes = "Production steady. Continue monitoring oven balance and resin delivery."


def now():
    return datetime.now(ZoneInfo(TIMEZONE))


def shift_label(dt):
    if 6 <= dt.hour < 14:
        return "Day Shift"
    if 14 <= dt.hour < 22:
        return "Afternoon Shift"
    return "Night Shift"


def fetch_data(force_simulation):
    """Return (raw_data, mode) where mode is "LIVE" or "SIMULATION"."""
    if force_simulation:
        return simulate_raw(), "SIMULATION"
    plc = FactoryPLC()
    try:
        if not plc.connect():
            return simulate_raw(), "SIMULATION"
        return plc.read_all(), "LIVE"
    finally:
        plc.close()


# ---------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Controls")
    auto_refresh = st.toggle("Auto-refresh", value=True)
    interval = st.slider("Refresh every (seconds)", 2, 60, REFRESH_SECONDS, disabled=not auto_refresh)
    force_sim = st.checkbox("Force simulation mode", help="Use simulated data even if the PLC is reachable.")
    if st.button("Refresh now"):
        st.rerun()
    if st.button("Clear trend history"):
        st.session_state.ticks = pd.DataFrame()
    st.divider()
    st.subheader("Shift Notes")
    st.text_area(
        "Operator log",
        key="operator_notes",
        height=160,
        help="Notes for shift handover, interventions, or process observations. Included in the CSV report.",
    )


# -------------------------------------------------------------- live dashboard
@st.fragment(run_every=interval if auto_refresh else None)
def dashboard():
    raw, mode = fetch_data(force_sim)
    failed = raw.get("failed", [])

    oven_data = ovens.process_ovens(raw.get("holding"))
    motor_data = motors.process_motors(raw.get("coils"), raw.get("holding"))
    sensor_data = sensors.process_sensors(raw.get("discrete"), raw.get("input_regs"))
    alert_list = alarms.evaluate_alarms(oven_data, motor_data, sensor_data)
    if failed:
        alert_list.insert(0, {"level": "WARN", "msg": f"PLC READ FAILED: {', '.join(failed)}"})

    crit = sum(a["level"] == "CRIT" for a in alert_list)
    warn = sum(a["level"] == "WARN" for a in alert_list)
    stats = oven_data["stats"]
    drive = motor_data["main_drive"]
    pump = motor_data["hydraulic_pump"]
    ts = now()
    running = any(oven_data[f"oven{i}"]["running"] for i in range(1, 7))

    st.title(DASHBOARD_TITLE)
    st.caption(
        f"PLC: {mode} • {ts.strftime('%A, %d %b %Y • %H:%M:%S')} • {shift_label(ts)}"
    )

    if mode == "SIMULATION":
        reason = "forced from the sidebar" if force_sim else f"PLC unreachable at {PLC_CONFIG['ip']}:{PLC_CONFIG['port']}"
        st.markdown(
            f"<div class='alert-banner alert-warn'>SIMULATED DATA ({reason}). Values below are not from the plant.</div>",
            unsafe_allow_html=True,
        )

    if crit:
        st.markdown(f"<div class='alert-banner alert-crit'>CRITICAL ALERTS: {crit} active</div>", unsafe_allow_html=True)
    elif warn:
        st.markdown(f"<div class='alert-banner alert-warn'>WARNINGS: {warn} active</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='alert-banner alert-ok'>SYSTEM HEALTHY: No active alarms</div>", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Plant Status", "RUNNING" if running else "IDLE", delta="Production view")
    k2.metric("Average Oven Temp", f"{stats['avg_temp']:.1f}°C", delta=f"Spread {stats['delta_max_min']:.1f}°C")
    k3.metric("Line Speed", f"{drive['speed_actual']:.1f} m/min", delta=f"Setpoint {drive['speed_setpoint']:.1f}")
    k4.metric("Critical Alerts", crit, delta=f"{warn} warnings")

    st.subheader("Oven & Process Overview")
    oven_cols = st.columns(3)
    for idx in range(6):
        oven = oven_data[f"oven{idx + 1}"]
        with oven_cols[idx % 3]:
            style = {"OK": "alert-ok", "WARNING": "alert-warn"}.get(oven["status"], "alert-crit")
            st.markdown(f"<div class='alert-banner {style}'>Oven {idx + 1} • {oven['status']}</div>", unsafe_allow_html=True)
            st.metric("Actual", f"{oven['actual']:.1f}°C", delta=f"{oven['delta']:+.1f}°C vs setpoint {oven['setpoint']:.1f}°C")
            st.progress(min(max(oven["actual"] / max(oven["setpoint"], 1), 0), 1))

    st.subheader("Production Line Status")
    left, center, right = st.columns(3)
    with left:
        st.markdown("<div class='metric-tag'>DRIVES</div>", unsafe_allow_html=True)
        st.markdown(
            f"""<div class='status-box'>
            <strong>Main Drive:</strong> {'RUNNING' if drive['run'] else 'STOPPED'}<br>
            <strong>Speed:</strong> {drive['speed_actual']:.1f} m/min<br>
            <strong>Setpoint:</strong> {drive['speed_setpoint']:.1f} m/min</div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""<div class='status-box'>
            <strong>Hydraulic Pump:</strong> {'RUNNING' if pump['run'] else 'STOPPED'}<br>
            <strong>Pressure:</strong> {pump['pressure']:.1f} bar</div>""",
            unsafe_allow_html=True,
        )
    with center:
        st.markdown("<div class='metric-tag'>SAFETY</div>", unsafe_allow_html=True)
        st.metric("E-Stop", "OK" if sensor_data["e_stop_ok"] else "TRIPPED")
        st.metric("Resin Level", "LOW" if sensor_data["resin_low"] else "OK")
        st.metric("Board Sensor", "PRESENT" if sensor_data["board_present"] else "ABSENT")
    with right:
        st.markdown("<div class='metric-tag'>PROCESS</div>", unsafe_allow_html=True)
        st.metric("Line Temp", f"{sensor_data['line_temp']:.1f}°C")
        st.metric("Unwinder", "RUNNING" if motor_data["unwinder"]["run"] else "STOPPED")
        st.metric("Rewinder", "RUNNING" if motor_data["rewinder"]["run"] else "STOPPED")

    # Trend history (kept per browser session)
    row = {"time": ts.replace(tzinfo=None), "line_speed": drive["speed_actual"], "alarm_count": len(alert_list)}
    row.update({f"oven{i}": oven_data[f"oven{i}"]["actual"] for i in range(1, 7)})
    st.session_state.ticks = pd.concat(
        [st.session_state.ticks, pd.DataFrame([row])], ignore_index=True
    ).tail(TREND_POINTS)
    ticks = st.session_state.ticks

    st.subheader("Trend Monitoring")
    fig = go.Figure()
    for i in range(1, 7):
        fig.add_trace(go.Scatter(x=ticks["time"], y=ticks[f"oven{i}"], mode="lines", name=f"Oven {i}", line=dict(width=2)))
    fig.update_layout(template="plotly_white", height=420, legend_title_text="Ovens",
                      xaxis_title="Time", yaxis_title="Temperature (°C)")
    st.plotly_chart(fig)

    st.subheader("Alarm Intelligence")
    if alert_list:
        alert_df = pd.DataFrame(alert_list)
        alert_df["severity"] = alert_df["level"].map({"CRIT": "Critical", "WARN": "Warning"})
        st.dataframe(alert_df[["severity", "msg"]], hide_index=True)
    else:
        st.success("No alarms raised. All monitored systems are in stable operating range.")

    st.subheader("Operational Summary")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Avg oven temp", f"{stats['avg_temp']:.1f}°C")
    s2.metric("Oven spread", f"{stats['delta_max_min']:.1f}°C")
    s3.metric("Drive speed", f"{drive['speed_actual']:.1f} m/min")
    s4.metric("Maintenance flags", warn)

    report = pd.DataFrame([{ 
        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "shift": shift_label(ts),
        "data_source": mode,
        "avg_oven_temp": stats["avg_temp"],
        "line_speed": drive["speed_actual"],
        "critical_alerts": crit,
        "warning_alerts": warn,
        "e_stop_ok": sensor_data["e_stop_ok"],
        "resin_low": sensor_data["resin_low"],
        "operator_notes": st.session_state.get("operator_notes", ""),
    }])
    buf = io.StringIO()
    report.to_csv(buf, index=False)
    st.download_button(
        "Download shift report",
        data=buf.getvalue(),
        file_name=f"bizmastas_shift_report_{ts.strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
    st.caption("BizMastas © 2026 — Impregnation line production monitoring dashboard")


dashboard()
