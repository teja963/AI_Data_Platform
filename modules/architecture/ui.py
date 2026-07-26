import base64
import html
from pathlib import Path
from urllib.parse import quote
import zlib

import streamlit as st
import streamlit.components.v1 as components

from core.access import user_can_view_architecture
from core.architecture import (
    add_architecture_diagram,
    delete_architecture_diagram,
    get_architecture_diagrams,
)


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
DRAWIO_EXTENSIONS = {".drawio", ".dio"}


def _is_image_file(file_name, content_type):
    suffix = Path(file_name or "").suffix.lower()
    return (content_type or "").startswith("image/") or suffix in IMAGE_EXTENSIONS


def _is_drawio_file(file_name):
    return Path(file_name or "").suffix.lower() in DRAWIO_EXTENSIONS


def _drawio_viewer_url(file_data, title):
    xml = file_data.decode("utf-8")
    uri_encoded_xml = quote(xml, safe="~()*!.'-")
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(uri_encoded_xml.encode("utf-8")) + compressor.flush()
    payload = quote(base64.b64encode(compressed).decode("ascii"), safe="")
    safe_title = quote(title or "Architecture Diagram", safe="")
    return (
        "https://viewer.diagrams.net/"
        f"?highlight=0000ff&layers=1&nav=1&title={safe_title}#R{payload}"
    )


def _render_image_viewer(diagram):
    mime = diagram.content_type or "image/png"
    encoded = base64.b64encode(diagram.file_data).decode("ascii")
    safe_title = html.escape(diagram.title or diagram.file_name)
    components.html(
        f"""
        <style>
          html, body {{ margin: 0; height: 100%; overflow: hidden; background: #f6f7f9; }}
          #viewer {{ position: relative; height: 780px; width: 100%; overflow: auto; }}
          #diagram {{ display: block; width: 100%; height: auto; max-width: none; transform-origin: top left; }}
          #tools {{
            position: sticky; top: 10px; left: 10px; z-index: 5; display: inline-flex;
            gap: 6px; padding: 6px; border-radius: 8px; background: rgba(20,20,20,.78);
          }}
          button {{
            border: 0; background: transparent; color: white; font-size: 22px;
            width: 34px; height: 34px; cursor: pointer;
          }}
        </style>
        <div id="viewer" title="{safe_title}">
          <div id="tools">
            <button onclick="zoomBy(0.2)" title="Zoom in">+</button>
            <button onclick="zoomBy(-0.2)" title="Zoom out">−</button>
            <button onclick="resetZoom()" title="Reset zoom">↺</button>
            <button onclick="document.getElementById('viewer').requestFullscreen()" title="Full screen">⛶</button>
          </div>
          <img id="diagram" draggable="false" alt="{safe_title}" src="data:{mime};base64,{encoded}" />
        </div>
        <script>
          let scale = 1;
          const image = document.getElementById("diagram");
          function applyZoom() {{ image.style.transform = `scale(${{scale}})`; }}
          function zoomBy(delta) {{ scale = Math.min(4, Math.max(0.25, scale + delta)); applyZoom(); }}
          function resetZoom() {{ scale = 1; applyZoom(); }}
        </script>
        """,
        height=800,
        scrolling=False,
    )


def _render_admin_upload():
    with st.expander("Admin Upload Architecture Diagram", expanded=False):
        with st.form("architecture_upload_form", clear_on_submit=True):
            title = st.text_input("Diagram Title")
            description = st.text_area("Description / Notes", height=90)
            upload = st.file_uploader(
                "Upload diagram file",
                accept_multiple_files=False,
                help="Supports Draw.io files and any image or document format.",
            )
            submitted = st.form_submit_button("Upload Diagram", width="stretch")

        if submitted:
            if not title.strip() or upload is None:
                st.warning("Please provide a title and upload a file.")
                return

            add_architecture_diagram(
                username=st.session_state.get("user"),
                title=title.strip(),
                description=description.strip(),
                file_name=upload.name,
                content_type=upload.type,
                file_data=upload.getvalue(),
            )
            st.success("Architecture diagram uploaded.")
            st.rerun()


def render_architecture():
    username = st.session_state.get("user")
    role = st.session_state.get("role", "user")
    if not user_can_view_architecture(username, role):
        st.error("Architecture diagrams are restricted to the administrator and Harika Priya.")
        return

    st.title("Architecture Diagrams")
    st.caption("Read-only architecture viewer. Use zoom, navigation, and full-screen controls to inspect diagrams.")

    is_admin = role == "admin"
    if is_admin:
        _render_admin_upload()

    try:
        diagrams = get_architecture_diagrams()
    except Exception as error:
        st.error(f"Architecture diagrams are unavailable right now: {error}")
        return

    if not diagrams:
        st.info("No architecture diagrams uploaded yet.")
        return

    for diagram in diagrams:
        with st.container(border=True):
            st.subheader(diagram.title or diagram.file_name)
            if diagram.description:
                st.write(diagram.description)

            if _is_drawio_file(diagram.file_name):
                try:
                    components.iframe(
                        _drawio_viewer_url(diagram.file_data, diagram.title or diagram.file_name),
                        height=800,
                        scrolling=True,
                    )
                except (UnicodeDecodeError, zlib.error):
                    st.error("This Draw.io file could not be displayed.")
            elif _is_image_file(diagram.file_name, diagram.content_type):
                _render_image_viewer(diagram)
            else:
                st.info("Read-only preview is not available for this file type.")

            if is_admin and st.button("Delete", key=f"delete_arch_{diagram.id}"):
                delete_architecture_diagram(diagram.id)
                st.success("Diagram deleted.")
                st.rerun()
