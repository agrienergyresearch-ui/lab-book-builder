"""Streamlit interface for the Lab Book Builder."""

from __future__ import annotations

import hashlib
import re

import streamlit as st

from pdf_builder import PdfDocument, TOC_MARKER, build_booklet, page_count


st.set_page_config(
    page_title="Lab Book Builder | Technical Instructor Tools",
    page_icon="📘",
    layout="wide",
)


def file_id(name: str, data: bytes) -> str:
    return hashlib.sha256(name.encode("utf-8") + b"\0" + data).hexdigest()


def safe_filename(title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", title.strip()).strip("._")
    return f"{cleaned or 'lab_book'}.pdf"


def move_item(index: int, direction: int) -> None:
    destination = index + direction
    if 0 <= destination < len(st.session_state.order):
        order = st.session_state.order
        order[index], order[destination] = order[destination], order[index]
        st.session_state.pop("booklet", None)


def remove_item(document_id: str) -> None:
    st.session_state.order.remove(document_id)
    st.session_state.pop("booklet", None)


st.caption("TECHNICAL INSTRUCTOR TOOLS BY AGRIENERGY")
st.title("Lab Book Builder")
st.write(
    "Build customized, professionally organized lab booklets from your PDF lab sheets. "
    "Designed for technical education instructors."
)

uploads = st.file_uploader(
    "Upload PDF lab sheets",
    type=["pdf"],
    accept_multiple_files=True,
    help="You can select many PDFs at once. Files are processed only for this browser session.",
)

documents: list[PdfDocument] = []
for upload in uploads:
    data = upload.getvalue()
    documents.append(PdfDocument(file_id(upload.name, data), upload.name, data))

document_by_id = {document.document_id: document for document in documents}
current_ids = list(document_by_id)

if "order" not in st.session_state:
    st.session_state.order = [TOC_MARKER]

# Preserve the user's arrangement while adding new uploads and removing files no longer uploaded.
st.session_state.order = [
    item for item in st.session_state.order if item == TOC_MARKER or item in document_by_id
]
if TOC_MARKER not in st.session_state.order:
    st.session_state.order.insert(0, TOC_MARKER)
for document_id in current_ids:
    if document_id not in st.session_state.order:
        st.session_state.order.append(document_id)

if not documents:
    st.info("Start by selecting two or more PDF lab sheets above.")
    st.stop()

st.subheader("Arrange the booklet")
st.caption("Use the arrows to move a lab sheet or the table of contents. PDFs above the TOC are included in the booklet but not listed in the TOC.")

for index, item in enumerate(st.session_state.order):
    left, name_col, pages_col, up_col, down_col, remove_col = st.columns([0.35, 5.5, 1.1, 0.55, 0.55, 0.8])
    left.write(f"**{index + 1}.**")
    if item == TOC_MARKER:
        name_col.info("TABLE OF CONTENTS")
        pages_col.write("")
    else:
        document = document_by_id[item]
        name_col.write(document.name)
        try:
            pages_col.caption(f"{page_count(document)} pages")
        except Exception:
            pages_col.caption("Unreadable")

    up_col.button("↑", key=f"up-{item}", disabled=index == 0, on_click=move_item, args=(index, -1))
    down_col.button(
        "↓",
        key=f"down-{item}",
        disabled=index == len(st.session_state.order) - 1,
        on_click=move_item,
        args=(index, 1),
    )
    if item == TOC_MARKER:
        remove_col.write("")
    else:
        remove_col.button("Remove", key=f"remove-{item}", on_click=remove_item, args=(item,))

st.divider()
settings_col, action_col = st.columns([1.4, 1])
with settings_col:
    book_title = st.text_input("Lab book title", value="Lab Book")
    toc_title = st.text_input("Table of contents title", value="Table of Contents")
    include_toc = st.checkbox("Include table of contents", value=True)
    add_page_numbers = st.checkbox("Add page numbers", value=True)
    page_number_alignment = st.radio(
        "Page number position",
        options=["Left", "Center", "Right"],
        index=1,
        horizontal=True,
        disabled=not add_page_numbers,
    )

with action_col:
    st.write("")
    st.write("")
    if st.button("Build Lab Book", type="primary", use_container_width=True):
        try:
            with st.spinner("Building the booklet…"):
                st.session_state.booklet = build_booklet(
                    documents,
                    st.session_state.order,
                    toc_title=toc_title.strip() or "Table of Contents",
                    include_toc=include_toc,
                    add_page_numbers=add_page_numbers,
                    page_number_alignment=page_number_alignment,
                )
                st.session_state.output_name = safe_filename(book_title)
        except Exception as exc:
            st.session_state.pop("booklet", None)
            st.error(f"Could not build the booklet: {exc}")

    if st.session_state.get("booklet"):
        st.success("Your lab book is ready.")
        st.download_button(
            "Download Lab Book PDF",
            data=st.session_state.booklet,
            file_name=st.session_state.output_name,
            mime="application/pdf",
            use_container_width=True,
        )

st.divider()
st.caption(
    "Technical Instructor Tools by Agrienergy · © 2026 Agrienergy Research  |  "
    "Uploaded files are temporary and are not added to a public library."
)
