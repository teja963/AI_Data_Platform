import streamlit as st

try:
    from streamlit_adjustable_columns import adjustable_columns
except ImportError:  # pragma: no cover - deployment fallback
    adjustable_columns = None


def coding_columns(key):
    """Return two coding panes with a draggable, persistent divider."""
    if adjustable_columns is None:
        return st.columns([1, 1], gap="small")

    return adjustable_columns(
        [1, 1],
        gap="small",
        border=False,
        key=key,
    )
