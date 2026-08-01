import streamlit as st

from core.access import user_can_view_architecture
from modules.architecture.ui import render_diagram_collection
from modules.cloud.aws_lab import render_aws_practical_lab


def render_cloud():
    username = st.session_state.get("user")
    role = st.session_state.get("role", "user")
    if not user_can_view_architecture(username, role):
        st.error("Cloud Platform is restricted to the administrator and Harika Priya.")
        return

    st.title("Cloud Platform")
    aws_tab, gcp_tab, azure_tab = st.tabs(["AWS", "GCP", "Azure"])

    with aws_tab:
        practice_tab, diagrams_tab = st.tabs(["Practical Labs", "Architecture Diagrams"])
        with practice_tab:
            render_aws_practical_lab()
        with diagrams_tab:
            render_diagram_collection(
                title="AWS Architecture Diagrams",
                collection="cloud_aws",
                description="Read-only AWS Draw.io diagrams synchronized from GitHub.",
                key_prefix="cloud_aws",
                access_checked=True,
            )

    with gcp_tab:
        render_diagram_collection(
            title="GCP Architecture Diagrams",
            collection="cloud_gcp",
            description="Read-only GCP Draw.io diagrams synchronized from GitHub.",
            key_prefix="cloud_gcp",
            access_checked=True,
        )

    with azure_tab:
        render_diagram_collection(
            title="Azure Architecture Diagrams",
            collection="cloud_azure",
            description="Read-only Azure Draw.io diagrams synchronized from GitHub.",
            key_prefix="cloud_azure",
            access_checked=True,
        )
