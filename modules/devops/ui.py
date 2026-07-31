import streamlit as st

from core.access import user_can_view_architecture
from modules.architecture.ui import render_diagram_collection
from modules.devops.simulator_ui import render_kubernetes_simulator


def render_devops():
    username = st.session_state.get("user")
    role = st.session_state.get("role", "user")
    if not user_can_view_architecture(username, role):
        st.error("DevOps is restricted to the administrator and Harika Priya.")
        return

    st.title("DevOps")
    simulator_tab, diagrams_tab = st.tabs(
        ["Kubernetes Practice Lab", "Architecture Diagrams"]
    )
    with simulator_tab:
        render_kubernetes_simulator()
    with diagrams_tab:
        render_diagram_collection(
            title="DevOps Architecture Diagrams",
            collection="devops",
            description=(
                "Read-only DevOps Draw.io diagrams synchronized from GitHub. "
                "Use zoom, navigation, and full-screen controls."
            ),
            key_prefix="devops",
            access_checked=True,
        )
