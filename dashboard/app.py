"""Streamlit dashboard for the Predictive Intelligence demonstration.

Start the API first, then from the project root:
    streamlit run dashboard/app.py
The dashboard talks to the API over HTTP (set API_URL to point it elsewhere).
"""

import os
import sys
from pathlib import Path

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.cmapss import SENSOR_INFO  # noqa: E402
from src.visualization import theme  # noqa: E402

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
STATUS_COLOURS = {
    "no_measurable_wear": theme.TEAL, "early_wear": theme.BLUE,
    "advanced_wear": theme.AMBER, "near_end_of_predicted_life": theme.RED,
}

st.set_page_config(page_title="Predictive Intelligence", page_icon="✈", layout="wide")
theme.apply_theme()


@st.cache_data(ttl=300, show_spinner=False)
def api_get(path: str) -> dict:
    response = httpx.get(f"{API_URL}{path}", timeout=60)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict) -> dict:
    response = httpx.post(f"{API_URL}{path}", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def life_text(facts: dict) -> str:
    if facts["range_is_open_ended"]:
        return f"at least {facts['range_low_cycles']} flights"
    return f"{facts['range_low_cycles']} to {facts['range_high_cycles']} flights"


def estimate_chart(history: dict, facts: dict) -> go.Figure:
    estimates = pd.DataFrame(history["estimates"])
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=estimates["cycle"], y=estimates["high"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=estimates["cycle"], y=estimates["low"], fill="tonexty", line=dict(width=0),
                                fillcolor="rgba(74,144,217,0.25)", name="90% range"))
    figure.add_trace(go.Scatter(x=estimates["cycle"], y=estimates["estimate"], line=dict(color=theme.TEAL, width=2.5),
                                name="Estimate"))
    figure.add_hline(y=facts["rul_cap_cycles"], line=dict(color=theme.MUTED, dash="dot"),
                     annotation_text="model cannot see beyond this", annotation_font_color=theme.MUTED)
    figure.update_layout(title="How the estimate has changed over this engine's recorded life", height=380,
                         xaxis_title="Flights completed", yaxis_title="Estimated flights remaining",
                         legend=dict(orientation="h", y=1.12, x=0.6))
    return figure


def sensor_chart(history: dict, sensor: str) -> go.Figure:
    readings = pd.DataFrame(history["sensors"])
    symbol, description, unit = SENSOR_INFO[sensor]
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=readings["cycle"], y=readings[sensor], mode="lines",
                                line=dict(color=theme.SILVER, width=1), name="each flight", opacity=0.6))
    figure.add_trace(go.Scatter(x=readings["cycle"], y=readings[sensor].rolling(30, min_periods=1).mean(),
                                line=dict(color=theme.AMBER, width=2.5), name="30-flight average"))
    figure.update_layout(title=f"{description} ({symbol})", height=330, xaxis_title="Flights completed",
                         yaxis_title=unit, legend=dict(orientation="h", y=1.15, x=0.55))
    return figure


def reasons_chart(facts: dict) -> go.Figure:
    reasons = facts["main_reasons"][::-1]
    figure = go.Figure(go.Bar(
        x=[r["cycles"] for r in reasons], y=[f"{r['description']} ({r['symbol']})" for r in reasons], orientation="h",
        marker_color=[theme.AMBER if r["cycles"] < 0 else theme.TEAL for r in reasons]))
    figure.update_layout(title="Measurements that most influenced the estimate", height=300,
                         xaxis_title="Effect on the estimate (flights): amber lowers it, teal raises it")
    return figure


st.title("Predictive Intelligence")
st.caption("Engine health, remaining-life estimates and plain-language explanations · research demonstration on "
           "NASA C-MAPSS **simulated** data, not real aircraft")

try:
    engines = api_get("/engines")["engines"]
    model = api_get("/model")
except httpx.HTTPError as error:
    st.error(f"Cannot reach the API at {API_URL}. Start it with `uvicorn api.main:app` and reload. ({error})")
    st.stop()

with st.sidebar:
    st.header("Engine")
    engine_id = st.selectbox("Select an engine", engines, format_func=lambda i: f"Engine {i}")
    compare_id = st.selectbox("Compare with", [None, *engines], format_func=lambda i: "—" if i is None else f"Engine {i}")
    st.divider()
    st.header("Model")
    st.write(f"**{model['model']}**")
    st.write(f"Trained on: {model['trained_on']}")
    st.write(f"Typical error on unseen engines: about {model['typical_error_cycles']} flights")
    st.write(f"Range: {model['range']['target_coverage_percent']}% target, "
             f"{model['range']['measured_test_coverage_percent']:g}% measured on 100 test engines")
    st.info(model["notice"])

facts = api_get(f"/engines/{engine_id}")
history = api_get(f"/engines/{engine_id}/history")
overview_tab, sensors_tab, compare_tab, ask_tab = st.tabs(["Overview", "Sensor history", "Compare engines", "Ask a question"])

with overview_tab:
    colour = STATUS_COLOURS[facts["status"]["key"]]
    st.markdown(f"<div style='border-left:6px solid {colour};padding:0.6rem 1rem;background:{theme.PANEL};"
                f"border-radius:4px'><span style='font-size:1.3rem;font-weight:600;color:{colour}'>"
                f"{facts['status']['label']}</span><br>{facts['status']['plain']}</div>", unsafe_allow_html=True)
    st.write("")
    first, second, third = st.columns(3)
    first.metric("Estimated flights remaining", facts["estimate_cycles"])
    second.metric("Likely range", life_text(facts))
    third.metric("Flights recorded so far", facts["cycles_recorded"])
    st.caption("The range holds for about nine engines in ten. It is an estimate, not a guarantee, and not a safe "
               "operating window. " + ("A range of 'at least' means the model sees no sign of wear yet and cannot "
                                       "tell how much longer the engine will last." if facts["range_is_open_ended"] else ""))
    left, right = st.columns([3, 2])
    left.plotly_chart(estimate_chart(history, facts), width="stretch")
    right.plotly_chart(reasons_chart(facts), width="stretch")
    st.subheader("Something to consider")
    st.write(facts["status"]["consider"])
    st.caption(f"Status and suggestion are {facts['status']['basis']}.")
    with st.expander("What this system cannot tell you"):
        for limitation in facts["limitations"]:
            st.write(f"- {limitation}")

with sensors_tab:
    st.write("Each chart shows one measurement over the engine's recorded flights. The grey line is every flight; "
             "the amber line is the average of the last 30 flights, which shows the slow trend.")
    default = [r["sensor"] for r in facts["main_reasons"]]
    chosen = st.multiselect("Measurements", list(history["sensors"].keys() - {"cycle"}), default=default,
                            format_func=lambda s: f"{SENSOR_INFO[s][1]} ({SENSOR_INFO[s][0]})")
    columns = st.columns(2)
    for position, sensor in enumerate(chosen):
        columns[position % 2].plotly_chart(sensor_chart(history, sensor), width="stretch")

with compare_tab:
    if compare_id is None or compare_id == engine_id:
        st.write("Choose a second engine in the sidebar to compare.")
    else:
        other = api_get(f"/engines/{compare_id}")
        table = pd.DataFrame({
            f"Engine {engine_id}": [facts["status"]["label"], facts["estimate_cycles"], life_text(facts), facts["cycles_recorded"]],
            f"Engine {compare_id}": [other["status"]["label"], other["estimate_cycles"], life_text(other), other["cycles_recorded"]],
        }, index=["Status", "Estimated flights remaining", "Likely range", "Flights recorded"])
        st.table(table.astype(str))
        left, right = st.columns(2)
        left.plotly_chart(reasons_chart(facts).update_layout(title=f"Engine {engine_id}: main influences"), width="stretch")
        right.plotly_chart(reasons_chart(other).update_layout(title=f"Engine {compare_id}: main influences"), width="stretch")
        st.caption("The model does not use an engine's age. Two engines with the same number of flights can receive "
                   "very different estimates if their measurements have drifted by different amounts.")

with ask_tab:
    st.write(f"Ask about **Engine {engine_id}** in ordinary language. Answers are built only from this engine's "
             "model results.")
    suggestions = ["Is this engine healthy?", "How much longer can this engine work?",
                   "Why does the model think so?", "How reliable is this prediction?", "What should we do now?"]
    picked = st.pills("Suggestions", suggestions, label_visibility="collapsed")
    question = st.chat_input("Type a question about this engine")
    question = question or picked
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Preparing an answer…"):
                reply = api_post(f"/engines/{engine_id}/ask", {"question": question})
            st.write(reply["answer"])
            st.caption(f"Answer source: {reply['source']}" + (f" · {reply['note']}" if reply["note"] else ""))
