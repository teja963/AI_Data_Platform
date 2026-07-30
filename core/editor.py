import re

import streamlit as st

try:
    from code_editor import code_editor
except ImportError:  # pragma: no cover - optional UI dependency
    code_editor = None

from core.drafts import delete_draft, load_draft, save_draft


def _session_key_for_draft(draft_key):
    return f"editor_draft::{draft_key}"


def _ace_key(draft_key):
    version = st.session_state.get(_version_key(draft_key), 0)
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", draft_key)
    return f"ace_{normalized}_{version}"


def _response_key(draft_key):
    return f"editor_response::{draft_key}"


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

    action = None
    if code_editor is None:
        st.warning(
            "Code editor dependency is not installed, so Tab indentation and line numbers are unavailable. "
            "Deploy with `streamlit-code-editor` from requirements.txt to enable the full editor."
        )
        code = st.text_area(
            "Write Code",
            value=current_value,
            height=height,
            key=_text_area_key(draft_key),
            placeholder=placeholder,
            disabled=disabled,
        )
        run_col, submit_col, _ = st.columns([1, 1, 5])
        if run_col.button("▶", key=f"{_text_area_key(draft_key)}_run", disabled=disabled):
            action = "run"
        if submit_col.button("✓", key=f"{_text_area_key(draft_key)}_submit", disabled=disabled):
            action = "submit"
    else:
        buttons = [] if disabled else [
            {
                "name": "Run",
                "feather": "Play",
                "hasText": False,
                "alwaysOn": True,
                "commands": ["save-state", ["response", "run"]],
                "response": "run",
                "style": {"top": "0.4rem", "right": "3.6rem"},
            },
            {
                "name": "Submit",
                "feather": "Check",
                "primary": True,
                "hasText": False,
                "alwaysOn": True,
                "commands": ["save-state", ["response", "submit"]],
                "response": "submit",
                "style": {"top": "0.4rem", "right": "0.4rem"},
            },
        ]
        response = code_editor(
            current_value,
            lang=language,
            theme="dark",
            shortcuts="vscode",
            height=f"{height}px",
            allow_reset=True,
            response_mode="default",
            ghost_text=placeholder,
            buttons=buttons,
            options={
                "fontSize": 15,
                "tabSize": 4,
                "useSoftTabs": True,
                "wrap": False,
                "showPrintMargin": False,
                "readOnly": disabled,
            },
            props={
                "enableBasicAutocompletion": False,
                "enableLiveAutocompletion": False,
                "enableSnippets": False,
                "showGutter": True,
            },
            key=_ace_key(draft_key),
        )
        response_id = response.get("id") if response else None
        is_new_response = bool(
            response_id
            and response_id != st.session_state.get(_response_key(draft_key))
        )
        if is_new_response:
            st.session_state[_response_key(draft_key)] = response_id
            code = response.get("text", current_value)
            response_type = response.get("type")
            if not disabled and response_type in {"run", "submit"}:
                action = response_type
        else:
            code = current_value

    if code is None:
        code = st.session_state.get(session_key, current_value)

    if code != st.session_state.get(session_key):
        st.session_state[session_key] = code
        save_draft(draft_key, code)
    return code, action
