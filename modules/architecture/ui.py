import base64
import html
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import zlib

import streamlit as st
import streamlit.components.v1 as components

from core.access import user_can_view_architecture
from core.architecture import (
    add_github_architecture_diagram,
    delete_architecture_diagram,
    get_architecture_diagram,
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
        f"?highlight=0000ff&layers=1&nav=1&lightbox=1&border=8"
        f"&title={safe_title}#R{payload}"
    )


def _normalize_github_drawio_url(source_url):
    parsed = urlparse((source_url or "").strip())
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host == "raw.githubusercontent.com":
        raw_url = parsed._replace(query="", fragment="").geturl()
    elif host in {"github.com", "www.github.com"} and len(path_parts) >= 5 and path_parts[2] == "blob":
        owner, repository, _, branch, *file_parts = path_parts
        raw_path = "/".join([owner, repository, branch, *file_parts])
        raw_url = f"https://raw.githubusercontent.com/{raw_path}"
    else:
        raise ValueError("Use a GitHub file link or raw.githubusercontent.com link.")

    if Path(urlparse(raw_url).path).suffix.lower() not in DRAWIO_EXTENSIONS:
        raise ValueError("The GitHub link must point to a .drawio or .dio file.")
    return raw_url


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_github_drawio(raw_url):
    headers = {"User-Agent": "AI-Data-Engineering-Architecture-Viewer"}
    github_token = st.secrets.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    request = Request(raw_url, headers=headers)
    with urlopen(request, timeout=15) as response:
        file_data = response.read()
    if not file_data.strip():
        raise ValueError("The GitHub Draw.io file is empty.")
    xml = file_data.decode("utf-8")
    if "<mxfile" not in xml and "<mxGraphModel" not in xml:
        raise ValueError("The linked file is not valid Draw.io XML.")
    return file_data


def _render_image_viewer(diagram):
    mime = diagram.content_type or "image/png"
    encoded = base64.b64encode(diagram.file_data).decode("ascii")
    safe_title = html.escape(diagram.title or diagram.file_name)
    components.html(
        f"""
        <style>
          html, body {{ margin: 0; height: 100%; overflow: hidden; background: #f6f7f9; }}
          #viewer {{ position: relative; height: 780px; width: 100%; overflow: auto; }}
          #diagram {{ display: block; width: auto; height: auto; max-width: none; transform-origin: top left; }}
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
          const viewer = document.getElementById("viewer");
          const image = document.getElementById("diagram");
          function applyZoom() {{ image.style.transform = `scale(${{scale}})`; }}
          function zoomBy(delta) {{ scale = Math.min(4, Math.max(0.25, scale + delta)); applyZoom(); }}
          function fitZoom() {{
            if (!image.naturalWidth || !image.naturalHeight) return;
            scale = Math.min(4, Math.max(0.1, Math.min(
              viewer.clientWidth / image.naturalWidth,
              viewer.clientHeight / image.naturalHeight
            )));
            applyZoom();
          }}
          function resetZoom() {{ fitZoom(); }}
          image.addEventListener("load", fitZoom);
          new ResizeObserver(fitZoom).observe(viewer);
        </script>
        """,
        height=800,
        scrolling=False,
    )


def _render_drawio_viewer(file_data, title):
    config = {
        "highlight": "#0000ff",
        "nav": True,
        "resize": True,
        "fit": True,
        "border": 8,
        "toolbar": "zoom layers lightbox",
        "xml": file_data.decode("utf-8"),
    }
    encoded_config = html.escape(
        json.dumps(config, separators=(",", ":")),
        quote=True,
    )
    safe_title = html.escape(title or "Architecture Diagram")
    components.html(
        f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8">
            <style>
              html, body {{
                margin: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background: #f6f7f9;
              }}
              .viewer-shell {{
                width: 100%;
                height: 850px;
                overflow: hidden;
                background: #f6f7f9;
              }}
              .mxgraph {{
                width: 100%;
                height: 100%;
                border: 0;
              }}
            </style>
          </head>
          <body>
            <div class="viewer-shell" title="{safe_title}">
              <div class="mxgraph" data-mxgraph="{encoded_config}"></div>
            </div>
            <script src="https://viewer.diagrams.net/js/viewer-static.min.js"></script>
          </body>
        </html>
        """,
        height=870,
        scrolling=False,
    )


def _render_admin_upload(collection, key_prefix):
    with st.expander("Add GitHub Draw.io Diagram", expanded=False):
        with st.form(f"{key_prefix}_github_form", clear_on_submit=True):
            title = st.text_input("Diagram Title", key=f"{key_prefix}_title")
            description = st.text_area(
                "Description / Notes",
                height=90,
                key=f"{key_prefix}_description",
            )
            source_url = st.text_input(
                "GitHub Draw.io URL",
                placeholder="https://github.com/owner/repository/blob/main/diagrams/example.drawio",
                help="Paste the GitHub file link. The viewer reloads the latest file content from GitHub.",
                key=f"{key_prefix}_source_url",
            )
            submitted = st.form_submit_button("Add Diagram", width="stretch")

        if submitted:
            if not title.strip() or not source_url.strip():
                st.warning("Please provide a title and GitHub Draw.io URL.")
                return

            try:
                raw_url = _normalize_github_drawio_url(source_url)
                _fetch_github_drawio(raw_url)
                add_github_architecture_diagram(
                    username=st.session_state.get("user"),
                    title=title.strip(),
                    description=description.strip(),
                    file_name=Path(urlparse(raw_url).path).name,
                    source_url=raw_url,
                    collection=collection,
                )
                st.success("GitHub Draw.io diagram linked.")
                st.rerun()
            except (ValueError, UnicodeDecodeError, HTTPError, URLError, TimeoutError) as error:
                st.error(f"Could not link this GitHub Draw.io file: {error}")


def render_diagram_collection(
    title,
    collection,
    description,
    key_prefix,
    access_checked=False,
):
    role = st.session_state.get("role", "user")
    if not access_checked and not user_can_view_architecture(
        st.session_state.get("user"),
        role,
    ):
        st.error("Architecture diagrams are restricted to the administrator and Harika Priya.")
        return

    if title:
        st.header(title)
    if description:
        st.caption(description)

    is_admin = role == "admin"
    if is_admin:
        _render_admin_upload(collection, key_prefix)

    try:
        diagrams = get_architecture_diagrams(collection=collection)
    except Exception as error:
        st.error(f"Architecture diagrams are unavailable right now: {error}")
        return

    if not diagrams:
        st.info("No diagrams linked in this collection yet.")
        return

    diagram_by_id = {diagram.id: diagram for diagram in diagrams}
    selected_id = st.selectbox(
        "Diagram",
        list(diagram_by_id),
        format_func=lambda diagram_id: (
            diagram_by_id[diagram_id].title or diagram_by_id[diagram_id].file_name
        ),
        key=f"{key_prefix}_selected_diagram",
    )
    diagram = diagram_by_id[selected_id]
    with st.container(border=True):
        st.subheader(diagram.title or diagram.file_name)
        if diagram.description:
            st.write(diagram.description)

        if _is_drawio_file(diagram.file_name):
            try:
                file_data = (
                    _fetch_github_drawio(diagram.source_url)
                    if diagram.source_url
                    else get_architecture_diagram(diagram.id).file_data
                )
                _render_drawio_viewer(
                    file_data,
                    diagram.title or diagram.file_name,
                )
                if diagram.source_url:
                    st.caption("Read-only source: GitHub · synchronized within 60 seconds")
            except (ValueError, UnicodeDecodeError, HTTPError, URLError, TimeoutError, zlib.error) as error:
                st.error(f"This GitHub Draw.io file could not be displayed: {error}")
        elif _is_image_file(diagram.file_name, diagram.content_type):
            _render_image_viewer(get_architecture_diagram(diagram.id))
        else:
            st.info("Read-only preview is not available for this file type.")

        if is_admin and st.button("Delete", key=f"{key_prefix}_delete_{diagram.id}"):
            delete_architecture_diagram(diagram.id)
            st.success("Diagram deleted.")
            st.rerun()


@st.fragment
def render_architecture():
    st.title("Architecture Diagrams")
    render_diagram_collection(
        title=None,
        collection="architecture",
        description="Read-only architecture viewer. Use zoom, navigation, and full-screen controls to inspect diagrams.",
        key_prefix="architecture",
    )
