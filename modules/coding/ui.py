import streamlit as st

from modules.python.ui import render_python
from modules.sql.ui import render_sql

TRACKS = ["SQL / PySpark", "Python"]


def _get_query_param(name, default):
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def render_coding():
    st.sidebar.title("Coding Workspace")

    initial_track = _get_query_param("coding_track", TRACKS[0])
    if initial_track not in TRACKS:
        initial_track = TRACKS[0]

    if "coding_track" not in st.session_state or st.session_state.coding_track not in TRACKS:
        st.session_state.coding_track = initial_track

    track = st.sidebar.radio("Track", TRACKS, key="coding_track")
    st.query_params["coding_track"] = track

    if track == "Python":
        render_python(show_sidebar_title=False)
    else:
        render_sql(show_sidebar_title=False)
