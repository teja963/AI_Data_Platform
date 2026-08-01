import streamlit as st


def lazy_tab(options, key, label="Section"):
    """Render one tab body at a time instead of eagerly building every tab."""
    options = list(options)
    if not options:
        raise ValueError("lazy_tab requires at least one option")
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    selected = st.segmented_control(
        label,
        options,
        key=key,
        label_visibility="collapsed",
        width="stretch",
    )
    return selected or options[0]
