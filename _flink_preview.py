import streamlit as st

from modules.spark.flink_pipeline import render_compact_flink_simulator


st.set_page_config(page_title="Flink Simulator Preview", layout="wide")
render_compact_flink_simulator()
