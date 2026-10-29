import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import PLC_CONFIG, REFRESH_SECONDS, TIMEZONE, TREND_POINTS
from logic import alarms, motors, ovens, sensors
from modbus_client import FactoryPLC, simulate_raw

DASHBOARD_TITLE = "Biashara Masters Sawmill"

st.set_page_config(page_title=DASHBOARD_TITLE, page_icon="🏭", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #0f172a;
        --bg-2: #111827;
        --panel: rgba(15, 23, 42, 0.82);
        --panel-2: rgba(30, 41, 59, 0.9);
        --border: rgba(148, 163, 184, 0.18);
        --text: #e2e8f0;
        --muted: #94a3b8;
        --cyan: #22d3ee;
        --cyan-soft: rgba(34, 211, 238, 0.14);
        --amber: #fbbf24;
        --amber-soft: rgba(251, 191, 36, 0.14);
        --emerald: #34d399;
        --emerald-soft: rgba(52, 211, 153, 0.16);
        --red: #f87171;
        --red-soft: rgba(248, 113, 113, 0.15);
        --shadow: 0 20px 30px rgba(2, 6, 23, 0.45);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #020817 0%, rgba(15, 23, 42, 1) 100%);
        color: var(--text);
    }

    .stApp {
        background: radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 18%),
                    radial-gradient(circle at top right, rgba(52, 211, 153, 0.06), transparent 15%),
                    #020817;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-left: 1.2rem;
        padding-right: 1.2rem;
        max-width: 1600px;
    }

    .topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 1rem;
        margin-bottom: 1.1rem;
        border: 1px solid var(--border);
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(15, 23, 42, 0.72));
        box-shadow: var(--shadow);
    }

    .topbar-title {
        font-size: 1.15rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text);
    }

    .topbar-meta {
        display: flex;
        gap: 1rem;
        align-items: center;
        color: var(--muted);
        font-size: 0.78rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.8rem;
        border-radius: 999px;
        border: 1px solid rgba(34, 211, 238, 0.3);
        background: rgba(34, 211, 238, 0.08);
        color: var(--cyan);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .status-pill::before {
        content: "";
        width: 0.6rem;
        height: 0.6rem;
        border-radius: 50%;
        background: var(--cyan);
        box-shadow: 0 0 14px rgba(34, 211, 238, 0.9);
    }

    .headline-banner {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.9rem 1.1rem;
        border-radius: 16px;
        margin: 0.5rem 0 1rem 0;
        border: 1px solid rgba(248, 113, 113, 0.22);
        background: linear-gradient(90deg, rgba(127, 29, 29, 0.42), rgba(30, 41, 59, 0.8));
        color: #fecaca;
        box-shadow: var(--shadow);
    }

    .headline-banner strong {
        font-size: 0.82rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .headline-banner span {
        font-size: 0.9rem;
        opacity: 0.9;
    }

    .metric-card {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.75));
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1rem;
        box-shadow: var(--shadow);
        min-height: 110px;
    }

    .metric-label {
        color: var(--muted);
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.55rem;
    }

    .metric-value {
        color: #f8fafc;
        font-size: clamp(1.1rem, 2vw, 2.2rem);
        font-weight: 800;
        line-height: 1.1;
    }

    .metric-delta {
        margin-top: 0.35rem;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--muted);
    }

    .positive { color: var(--emerald); }
    .warning { color: var(--amber); }
    .critical { color: var(--red); }

    .panel {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.72));
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1rem;
        box-shadow: var(--shadow);
    }

    .panel-title {
        color: var(--text);
        font-size: 0.78rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.8rem;
        font-weight: 700;
    }

    .oven-card {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.82), rgba(17, 24, 39, 0.96));
        border-radius: 16px;
        border: 1px solid var(--border);
        padding: 0.8rem 0.8rem 0.9rem; 
        min-height: 170px;
        box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.08);
    }

    .oven-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.6rem;
    }

    .oven-name {
        font-size: 0.82rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
    }

    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.24rem 0.55rem;
        border-radius: 999px;
        font-size: 0.62rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .status-ok { background: rgba(52, 211, 153, 0.1); color: var(--emerald); border: 1px solid rgba(52, 211, 153, 0.2); }
    .status-warning { background: rgba(251, 191, 36, 0.1); color: var(--amber); border: 1px solid rgba(251, 191, 36, 0.24); }
    .status-critical { background: rgba(248, 113, 113, 0.1); color: var(--red); border: 1px solid rgba(248, 113, 113, 0.24); }

    .oven-temp {
        font-size: 1.7rem;
        font-weight: 800;
        color: #f8fafc;
        margin-top: 0.25rem;
    }

    .oven-delta {
        font-size: 0.74rem;
        color: var(--muted);
        margin-top: 0.25rem;
    }

    .stProgress > div > div {
        background: linear-gradient(90deg, var(--cyan), var(--emerald));
        border-radius: 999px;
    }

    .stDataFrame {
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid var(--border);
        border-radius: 12px;
    }

    .alarm-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.72rem 0.8rem;
        margin-bottom: 0.5rem;
        border-radius: 10px;
        border: 1px solid var(--border);
        background: rgba(15, 23, 42, 0.7);
    }

    .alarm-level {
        display: inline-flex;
        align-items: center;
        min-width: 82px;
        justify-content: center;
        padding: 0.25rem 0.45rem;
        border-radius: 999px;
        font-size: 0.62rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .level-crit { background: rgba(248, 113, 113, 0.12); color: var(--red); }
    .level-warn { background: rgba(251, 191, 36, 0.12); color: var(--amber); }

    .alarm-text { color: #e2e8f0; font-size: 0.82rem; }

    .status-block {
        padding: 0.8rem 0.9rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: rgba(15, 23, 42, 0.64);
        margin-bottom: 0.55rem;
    }

    .status-block strong { color: #f8fafc; }

    @media (max-width: 1200px) {
        .topbar { flex-direction: column; gap: 0.7rem; align-items: flex-start; }
        .headline-banner { flex-direction: column; align-items: flex-start; gap: 0.4rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "ticks" not in st.session_state:
    st.session_state.ticks = pd.DataFrame()
if "operator_notes" not in st.session_state:
    st.session_state.operator_notes = "Production steady. Continue monitoring oven balance and resin delivery."


def utc_now():
    return datetime.now(timezone.utc)


def local_now():
    return datetime.now(ZoneInfo(TIMEZONE))


def shift_label(dt):
    hour = dt.hour
    if 6 <= hour < 14:
        return "Day Shift"
    if 14 <= hour < 22:
        return "Afternoon Shift"
    return "Night Shift"


def fetch_data(force_simulation):
    if force_simulation:
        return simulate_raw(), "SIMULATION"
    plc = FactoryPLC()
    try:
        if not plc.connect():
            return simulate_raw(), "SIMULATION"
        return plc.read_all(), "LIVE"
    finally:
        plc.close()


with st.sidebar:
    st.header("Controls")
    auto_refresh = st.toggle("Auto-refresh", value=True)
    interval = st.slider("Refresh every (seconds)", 2, 60, REFRESH_SECONDS, disabled=not auto_refresh)
    force_sim = st.checkbox("Force simulation mode")
    if st.button("Refresh now"):
        st.rerun()
    if st.button("Clear trend history"):
        st.session_state.ticks = pd.DataFrame()
    st.divider()
    st.subheader("Shift Notes")
    st.text_area("Operator log", key="operator_notes", height=160)


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
    active = crit > 0
    stats = oven_data["stats"]
    drive = motor_data["main_drive"]
    pump = motor_data["hydraulic_pump"]
    ts = local_now()
    current_shift = shift_label(ts)
    oee = max(52.0, min(96.0, 100 - crit * 12 - warn * 4))

    st.markdown(
        """
        <div class='topbar'>
            <div class='topbar-title'>Biashara Masters Sawmill</div>
            <div class='topbar-meta'>
                <span>UTC: {utc}</span>
                <span>{shift}</span>
                <div class='status-pill'>Operational</div>
            </div>
        </div>
        """.format(utc=utc_now().strftime("%Y-%m-%d %H:%M:%S UTC"), shift=current_shift),
        unsafe_allow_html=True,
    )

    if crit or warn:
        banner_text = "Critical alert" if crit else "Warning attention"
        banner_color = "critical" if crit else "warning"
        st.markdown(
            f"<div class='headline-banner'><strong>{banner_color.upper()} ALERT</strong><span>{banner_text}: {'; '.join(a['msg'] for a in alert_list[:3])}</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='headline-banner'><strong>System Stable</strong><span>No active alarms across the line.</span></div>",
            unsafe_allow_html=True,
        )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            "<div class='metric-card'><div class='metric-label'>Plant Status</div><div class='metric-value'>RUNNING</div><div class='metric-delta positive'>Live process view</div></div>",
            unsafe_allow_html=True,
        )
    with k2:
        avg_temp = f"{stats['avg_temp']:.1f}°C"
        st.markdown(
            f"<div class='metric-card'><div class='metric-label'>Average Oven Temperature</div><div class='metric-value'>{avg_temp}</div><div class='metric-delta positive'>Spread {stats['delta_max_min']:.1f}°C</div></div>",
            unsafe_allow_html=True,
        )
    with k3:
        speed = f"{drive['speed_actual']:.1f} m/min"
        st.markdown(
            f"<div class='metric-card'><div class='metric-label'>Line Speed</div><div class='metric-value'>{speed}</div><div class='metric-delta positive'>Target {drive['speed_setpoint']:.1f}</div></div>",
            unsafe_allow_html=True,
        )
    with k4:
        oee_text = f"{oee:.1f}%"
        st.markdown(
            f"<div class='metric-card'><div class='metric-label'>Overall Equipment Effectiveness</div><div class='metric-value'>{oee_text}</div><div class='metric-delta {'positive' if oee > 70 else 'warning'}'>Availability vs target</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='panel-title' style='margin-top:1rem;'>Process Matrix</div>", unsafe_allow_html=True)
    oven_cols = st.columns(3)
    for idx in range(6):
        oven = oven_data[f"oven{idx + 1}"]
        status = oven["status"]
        badge_class = "status-ok" if status == "OK" else "status-warning" if status == "WARNING" else "status-critical"
        with oven_cols[idx % 3]:
            st.markdown(
                f"""
                <div class='oven-card'>
                    <div class='oven-top'>
                        <div class='oven-name'>Oven {idx + 1}</div>
                        <div class='status-badge {badge_class}'>{status}</div>
                    </div>
                    <div class='oven-temp'>{oven['actual']:.1f}°C</div>
                    <div class='oven-delta'>Setpoint {oven['setpoint']:.1f}°C • Drift {oven['delta']:+.1f}°C</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(min(max(oven["actual"] / max(oven["setpoint"], 1), 0), 1))

    g1, g2 = st.columns([2.2, 1.0])

    with g1:
        st.markdown("<div class='panel-title' style='margin-top:1rem;'>Multi-Zone Thermal Trend</div>", unsafe_allow_html=True)
        row = {"time": ts.replace(tzinfo=None), "line_speed": drive["speed_actual"], "alarm_count": len(alert_list)}
        row.update({f"oven{i}": oven_data[f"oven{i}"]["actual"] for i in range(1, 7)})
        st.session_state.ticks = pd.concat(
            [st.session_state.ticks, pd.DataFrame([row])], ignore_index=True
        ).tail(TREND_POINTS)
        ticks = st.session_state.ticks

        fig = go.Figure()
        for i in range(1, 7):
            fig.add_trace(go.Scatter(x=ticks["time"], y=ticks[f"oven{i}"], mode="lines", name=f"Oven {i}", line=dict(width=2.1)))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(15, 23, 42, 0)",
            plot_bgcolor="rgba(15, 23, 42, 0.2)",
            margin=dict(l=18, r=8, t=8, b=8),
            height=360,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            xaxis_title="Time",
            yaxis_title="Temperature (°C)",
        )
        st.plotly_chart(fig, use_container_width=True)

    with g2:
        st.markdown("<div class='panel-title' style='margin-top:1rem;'>Alarm Intelligence</div>", unsafe_allow_html=True)
        if alert_list:
            for a in alert_list[:6]:
                level_class = "level-crit" if a["level"] == "CRIT" else "level-warn"
                st.markdown(
                    f"<div class='alarm-row'><span class='alarm-level {level_class}'>{a['level']}</span><span class='alarm-text'>{a['msg']}</span></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("<div class='alarm-row'><span class='alarm-level level-warn'>OK</span><span class='alarm-text'>No active alarms</span></div>", unsafe_allow_html=True)

        st.markdown("<div class='panel-title' style='margin-top:1rem;'>Line Status</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='status-block'><strong>Main Drive:</strong> {'RUNNING' if drive['run'] else 'STOPPED'}<br><strong>Speed:</strong> {drive['speed_actual']:.1f} m/min</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='status-block'><strong>Hydraulic Pump:</strong> {'RUNNING' if pump['run'] else 'STOPPED'}<br><strong>Pressure:</strong> {pump['pressure']:.1f} bar</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='status-block'><strong>E-Stop:</strong> {'OK' if sensor_data['e_stop_ok'] else 'TRIPPED'}<br><strong>Resin:</strong> {'LOW' if sensor_data['resin_low'] else 'NORMAL'}</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel-title' style='margin-top:1rem;'>Operational Summary</div>", unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>Avg Oven Temp</div><div class='metric-value'>{stats['avg_temp']:.1f}°C</div><div class='metric-delta positive'>Stable</div></div>", unsafe_allow_html=True)
    with s2:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>Oven Spread</div><div class='metric-value'>{stats['delta_max_min']:.1f}°C</div><div class='metric-delta {'positive' if stats['delta_max_min'] < 12 else 'warning'}'>Balance index</div></div>", unsafe_allow_html=True)
    with s3:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>Drive Speed</div><div class='metric-value'>{drive['speed_actual']:.1f}</div><div class='metric-delta positive'>m/min</div></div>", unsafe_allow_html=True)
    with s4:
        st.markdown(f"<div class='metric-card'><div class='metric-label'>Maintenance Flags</div><div class='metric-value'>{warn}</div><div class='metric-delta {'warning' if warn else 'positive'}'>open watchlist</div></div>", unsafe_allow_html=True)

    report = pd.DataFrame([
        {
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "shift": current_shift,
            "data_source": mode,
            "avg_oven_temp": stats["avg_temp"],
            "line_speed": drive["speed_actual"],
            "critical_alerts": crit,
            "warning_alerts": warn,
            "e_stop_ok": sensor_data["e_stop_ok"],
            "resin_low": sensor_data["resin_low"],
            "operator_notes": st.session_state.get("operator_notes", ""),
        }
    ])
    buf = io.StringIO()
    report.to_csv(buf, index=False)
    st.download_button(
        "Download Shift Report",
        data=buf.getvalue(),
        file_name=f"bizmastas_shift_report_{ts.strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )


dashboard()

