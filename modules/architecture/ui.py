from pathlib import Path

import streamlit as st

from core.architecture import (
    add_architecture_diagram,
    delete_architecture_diagram,
    get_architecture_diagrams,
)


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


def _is_image_file(file_name, content_type):
    suffix = Path(file_name or "").suffix.lower()
    return (content_type or "").startswith("image/") or suffix in IMAGE_EXTENSIONS


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
    st.title("Architecture Diagrams")
    st.caption("Admin can upload Draw.io files, images, or other diagram assets. All users can view and download them.")

    is_admin = st.session_state.get("role") == "admin"
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

            if _is_image_file(diagram.file_name, diagram.content_type):
                st.image(diagram.file_data, caption=diagram.file_name, width="stretch")
            else:
                st.info("Preview is not available for this file type. Download it to open in the correct tool.")

            col1, col2 = st.columns([3, 1])
            col1.download_button(
                "Download Diagram",
                data=diagram.file_data,
                file_name=diagram.file_name,
                mime=diagram.content_type or "application/octet-stream",
                key=f"download_arch_{diagram.id}",
                width="stretch",
            )

            if is_admin and col2.button("Delete", key=f"delete_arch_{diagram.id}", width="stretch"):
                delete_architecture_diagram(diagram.id)
                st.success("Diagram deleted.")
                st.rerun()
