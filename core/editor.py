import re

import streamlit as st

try:
    from streamlit_ace import st_ace
except ImportError:  # pragma: no cover - optional UI dependency
    st_ace = None

from core.drafts import delete_draft, load_draft, save_draft


def _session_key_for_draft(draft_key):
    return f"editor_draft::{draft_key}"


def _ace_key(draft_key):
    version = st.session_state.get(_version_key(draft_key), 0)
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", draft_key)
    return f"ace_{normalized}_{version}"


def _version_key(draft_key):
    return f"editor_version::{draft_key}"


def _text_area_key(draft_key):
    return "textarea_" + re.sub(r"[^a-zA-Z0-9_]+", "_", draft_key)


def set_editor_draft(draft_key, value):
    session_key = _session_key_for_draft(draft_key)
    st.session_state[session_key] = value
    save_draft(draft_key, value)
    st.session_state[_version_key(draft_key)] = st.session_state.get(_version_key(draft_key), 0) + 1


def clear_editor_draft(draft_key):
    session_key = _session_key_for_draft(draft_key)
    st.session_state[session_key] = ""
    delete_draft(draft_key)
    st.session_state[_version_key(draft_key)] = st.session_state.get(_version_key(draft_key), 0) + 1


def get_editor_draft(draft_key, starter):
    session_key = _session_key_for_draft(draft_key)
    if session_key not in st.session_state:
        st.session_state[session_key] = load_draft(draft_key, starter)
    return st.session_state[session_key]


def render_code_editor(draft_key, language, starter, height=520, placeholder=None, disabled=False):
    session_key = _session_key_for_draft(draft_key)
    current_value = get_editor_draft(draft_key, starter)
    placeholder = placeholder or starter

    if st_ace is None:
        code = st.text_area(
            "Write Code",
            value=current_value,
            height=height,
            key=_text_area_key(draft_key),
            placeholder=placeholder,
            disabled=disabled,
        )
    else:
        line_count = max(18, int(height / 24))
        code = st_ace(
            value=current_value,
            placeholder=placeholder,
            language=language,
            theme="textmate",
            keybinding="vscode",
            min_lines=line_count,
            max_lines=line_count,
            font_size=14,
            tab_size=4,
            wrap=True,
            show_gutter=True,
            show_print_margin=False,
            readonly=disabled,
            auto_update=True,
            key=_ace_key(draft_key),
        )

    if code is None:
        code = st.session_state.get(session_key, current_value)

    if code != st.session_state.get(session_key):
        st.session_state[session_key] = code
        save_draft(draft_key, code)
    return code
