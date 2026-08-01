import streamlit as st

from core.access import user_can_view_architecture
from core.lazy_tabs import lazy_tab
from modules.architecture.ui import render_diagram_collection
from modules.cloud.aws_lab import render_aws_practical_lab


def render_cloud():
    username = st.session_state.get("user")
    role = st.session_state.get("role", "user")
    if not user_can_view_architecture(username, role):
        st.error("Cloud Platform is restricted to the administrator and Harika Priya.")
        return

    st.title("Cloud Platform")
    provider = lazy_tab(["AWS", "GCP", "Azure"], "cloud_active_provider", "Cloud provider")

    if provider == "AWS":
        aws_view = lazy_tab(
            ["Practical Labs", "Architecture Diagrams"],
            "cloud_aws_active_view",
            "AWS workspace",
        )
        if aws_view == "Practical Labs":
            render_aws_practical_lab()
        else:
            render_diagram_collection(
                title="AWS Architecture Diagrams",
                collection="cloud_aws",
                description="Read-only AWS Draw.io diagrams synchronized from GitHub.",
                key_prefix="cloud_aws",
                access_checked=True,
            )

    elif provider == "GCP":
        render_diagram_collection(
            title="GCP Architecture Diagrams",
            collection="cloud_gcp",
            description="Read-only GCP Draw.io diagrams synchronized from GitHub.",
            key_prefix="cloud_gcp",
            access_checked=True,
        )

    else:
        render_diagram_collection(
            title="Azure Architecture Diagrams",
            collection="cloud_azure",
            description="Read-only Azure Draw.io diagrams synchronized from GitHub.",
            key_prefix="cloud_azure",
            access_checked=True,
        )
