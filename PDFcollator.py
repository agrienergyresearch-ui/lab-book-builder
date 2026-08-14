import io
from pathlib import Path
from typing import List, Tuple, Union, Optional

import tkinter as tk
from tkinter import filedialog, messagebox

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    from PyPDF2 import PdfReader, PdfWriter  # type: ignore


TOC_MARKER = "__TOC__"
TOC_DISPLAY = "--- [TOC] Table of Contents ---"
Item = Union[Path, str]  # Path = a PDF; str = TOC_MARKER


def gather_pdfs_in_folder(folder: Path) -> List[Path]:
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])


def read_page_counts(pdf_paths: List[Path]) -> List[Tuple[Path, int]]:
    results = []
    for p in pdf_paths:
        reader = PdfReader(str(p))
        results.append((p, len(reader.pages)))
    return results


def make_toc_pdf(entries: List[Tuple[str, int, int]], title: str = "Table of Contents") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    left = 0.75 * inch
    right = 0.75 * inch
    top = height - 0.75 * inch
    bottom = 0.75 * inch

    c.setFont("Helvetica-Bold", 18)
    c.drawString(left, top, title)

    y = top - 0.5 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Document")
    c.drawString(width - right - 1.6 * inch, y, "Start Page")
    c.drawString(width - right - 0.7 * inch, y, "Pages")
    y -= 0.2 * inch

    c.setLineWidth(1)
    c.line(left, y, width - right, y)
    y -= 0.25 * inch

    c.setFont("Helvetica", 10)
    max_name_width = (width - left - right) - (1.6 * inch + 0.8 * inch)

    for name, start_page, page_count in entries:
        if y < bottom + 0.5 * inch:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(left, y, "(More entries than fit on one page. Extend TOC to multiple pages if needed.)")
            break

        display = name
        while c.stringWidth(display, "Helvetica", 10) > max_name_width and len(display) > 4:
            display = display[:-4] + "…"

        c.drawString(left, y, display)
        c.drawRightString(width - right - 1.0 * inch, y, str(start_page))
        c.drawRightString(width - right, y, str(page_count))
        y -= 0.22 * inch

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(left, bottom - 0.1 * inch, "Folder PDFs combined into one document")
    c.showPage()
    c.save()
    return buf.getvalue()


def make_pagenum_overlay(page_width: float, page_height: float, page_num: int, alignment: str = "center") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))
    c.setFont("Helvetica", 10)

    y = 0.4 * inch
    margin = 0.75 * inch
    if alignment == "left":
        c.drawString(margin, y, str(page_num))
    elif alignment == "right":
        c.drawRightString(page_width - margin, y, str(page_num))
    else:
        c.drawCentredString(page_width / 2, y, str(page_num))

    c.showPage()
    c.save()
    return buf.getvalue()


def split_items_around_toc(items: List[Item]) -> Tuple[List[Path], List[Path]]:
    """Return (pre_toc_pdfs, post_toc_pdfs). If no TOC marker, TOC assumed at start."""
    if TOC_MARKER in items:
        idx = items.index(TOC_MARKER)
        pre = [x for x in items[:idx] if isinstance(x, Path)]
        post = [x for x in items[idx + 1 :] if isinstance(x, Path)]
        return pre, post
    else:
        # default: TOC at the top (no pre)
        post = [x for x in items if isinstance(x, Path)]
        return [], post


def combine_with_movable_toc_and_numbers(
    ordered_items: List[Item],
    output_pdf: Path,
    toc_title: str,
    page_num_alignment: str = "center",
) -> None:
    # Split based on TOC marker
    pre_pdfs, post_pdfs = split_items_around_toc(ordered_items)
    all_pdfs = pre_pdfs + post_pdfs
    if not all_pdfs:
        raise ValueError("No PDFs selected to combine.")

    # Compute TOC entries start pages based on:
    # pre_pdfs pages + TOC page(s) (assumed 1 for now) + each post_pdfs
    pre_counts = read_page_counts(pre_pdfs) if pre_pdfs else []
    post_counts = read_page_counts(post_pdfs) if post_pdfs else []

    pre_pages = sum(n for _, n in pre_counts)
    toc_pages_assumed = 1  # current TOC generator makes 1 page

    # TOC starts after the pre-pages
    toc_start_page = pre_pages + 1  # (because pages are 1-indexed)
    # Documents listed in TOC are the ones after TOC (post_pdfs)
    entries = []
    current_start = toc_start_page + toc_pages_assumed
    for p, n_pages in post_counts:
        entries.append((p.name, current_start, n_pages))
        current_start += n_pages

    # Build output
    writer = PdfWriter()

    # Add pre-PDFs
    for pdf_path in pre_pdfs:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)

    # Add TOC
    toc_bytes = make_toc_pdf(entries, title=toc_title)
    toc_reader = PdfReader(io.BytesIO(toc_bytes))
    for page in toc_reader.pages:
        writer.add_page(page)

    # Add post-PDFs
    for pdf_path in post_pdfs:
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)

    # Add page numbers to all pages
    total_pages = len(writer.pages)
    for i in range(total_pages):
        page = writer.pages[i]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)

        overlay_bytes = make_pagenum_overlay(w, h, i + 1, page_num_alignment)
        overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
        page.merge_page(overlay_reader.pages[0])

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pdf, "wb") as f:
        writer.write(f)


class PdfOrderApp:
    def __init__(self, root: tk.Tk, folder: Path, pdfs: List[Path]):
        self.root = root
        self.folder = folder

        # Page number alignment checkboxes (center selected by default).
        self.page_num_alignment = tk.StringVar(value="center")

        # Items list includes PDFs + a movable TOC marker (default: at top)
        self.items: List[Item] = [TOC_MARKER] + list(pdfs)

        root.title("PDF Collator - Choose Order (move TOC)")
        root.geometry("900x560")

        top = tk.Frame(root)
        top.pack(fill="x", padx=10, pady=(10, 0))

        self.folder_label = tk.Label(top, text=f"Folder: {folder}", anchor="w")
        self.folder_label.pack(fill="x")

        mid = tk.Frame(root)
        mid.pack(fill="both", expand=True, padx=10, pady=10)

        self.listbox = tk.Listbox(mid, selectmode=tk.EXTENDED)
        self.listbox.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(mid, orient="vertical", command=self.listbox.yview)
        sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        right = tk.Frame(mid)
        right.pack(side="left", fill="y", padx=(10, 0))

        tk.Button(right, text="Move Up", width=16, command=self.move_up).pack(pady=3)
        tk.Button(right, text="Move Down", width=16, command=self.move_down).pack(pady=3)
        tk.Button(right, text="Remove (PDF only)", width=16, command=self.remove).pack(pady=12)

        tk.Button(right, text="Sort PDFs A→Z", width=16, command=self.sort_pdfs_az).pack(pady=3)
        tk.Button(right, text="Sort PDFs Z→A", width=16, command=self.sort_pdfs_za).pack(pady=3)
        tk.Button(right, text="Insert TOC Here", width=16, command=self.insert_toc_here).pack(pady=12)

        tk.Label(right, text="Page Number Position").pack(pady=(12, 2))
        tk.Checkbutton(
            right, text="Left", variable=self.page_num_alignment,
            onvalue="left", offvalue="", command=lambda: self._set_page_alignment("left")
        ).pack(anchor="w")
        tk.Checkbutton(
            right, text="Center", variable=self.page_num_alignment,
            onvalue="center", offvalue="", command=lambda: self._set_page_alignment("center")
        ).pack(anchor="w")
        tk.Checkbutton(
            right, text="Right", variable=self.page_num_alignment,
            onvalue="right", offvalue="", command=lambda: self._set_page_alignment("right")
        ).pack(anchor="w")

        bottom = tk.Frame(root)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        tk.Button(bottom, text="Pick Different Folder", command=self.pick_new_folder).pack(side="left")
        tk.Button(bottom, text="Build PDF…", command=self.build_pdf).pack(side="right")
        tk.Button(bottom, text="Quit", command=root.destroy).pack(side="right", padx=(0, 8))

        self.refresh()

    def _set_page_alignment(self, alignment: str):
        # Keep exactly one page-number position selected.
        self.page_num_alignment.set(alignment)

    def _display_text(self, item: Item) -> str:
        if item == TOC_MARKER:
            return TOC_DISPLAY
        assert isinstance(item, Path)
        return item.name

    def refresh(self):
        self.listbox.delete(0, tk.END)
        for it in self.items:
            self.listbox.insert(tk.END, self._display_text(it))

    def move_up(self):
        sel = list(self.listbox.curselection())
        if not sel or sel[0] == 0:
            return
        for i in sel:
            self.items[i - 1], self.items[i] = self.items[i], self.items[i - 1]
        self.refresh()
        for i in [s - 1 for s in sel]:
            self.listbox.selection_set(i)

    def move_down(self):
        sel = list(self.listbox.curselection())
        if not sel or sel[-1] == len(self.items) - 1:
            return
        for i in reversed(sel):
            self.items[i + 1], self.items[i] = self.items[i], self.items[i + 1]
        self.refresh()
        for i in [s + 1 for s in sel]:
            self.listbox.selection_set(i)

    def remove(self):
        sel = list(self.listbox.curselection())
        if not sel:
            return
        # Remove only PDFs; never remove TOC marker
        for i in reversed(sel):
            if self.items[i] == TOC_MARKER:
                continue
            del self.items[i]
        self.refresh()

    def sort_pdfs_az(self):
        # Keep TOC marker at current position; sort PDFs around it
        pre, post = split_items_around_toc(self.items)
        pre_sorted = sorted(pre, key=lambda p: p.name.lower())
        post_sorted = sorted(post, key=lambda p: p.name.lower())
        if TOC_MARKER in self.items:
            idx = self.items.index(TOC_MARKER)
            self.items = pre_sorted + [TOC_MARKER] + post_sorted
        else:
            self.items = [TOC_MARKER] + post_sorted
        self.refresh()

    def sort_pdfs_za(self):
        pre, post = split_items_around_toc(self.items)
        pre_sorted = sorted(pre, key=lambda p: p.name.lower(), reverse=True)
        post_sorted = sorted(post, key=lambda p: p.name.lower(), reverse=True)
        if TOC_MARKER in self.items:
            self.items = pre_sorted + [TOC_MARKER] + post_sorted
        else:
            self.items = [TOC_MARKER] + post_sorted
        self.refresh()

    def insert_toc_here(self):
        # Move TOC marker to just after the highest-selected index
        sel = list(self.listbox.curselection())
        if not sel:
            return
        insert_after = max(sel)

        # Remove existing TOC marker
        if TOC_MARKER in self.items:
            old = self.items.index(TOC_MARKER)
            del self.items[old]
            if old <= insert_after:
                insert_after -= 1

        self.items.insert(insert_after + 1, TOC_MARKER)
        self.refresh()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(insert_after + 1)

    def pick_new_folder(self):
        folder_selected = filedialog.askdirectory(title="Select folder containing PDF lab sheets")
        if not folder_selected:
            return
        folder = Path(folder_selected)
        pdfs = gather_pdfs_in_folder(folder)
        if not pdfs:
            messagebox.showerror("No PDFs Found", f"No PDF files were found in:\n{folder}")
            return
        self.folder = folder
        self.folder_label.config(text=f"Folder: {folder}")
        self.items = [TOC_MARKER] + list(pdfs)
        self.refresh()

    def build_pdf(self):
        # Need at least one PDF somewhere
        any_pdf = any(isinstance(x, Path) for x in self.items)
        if not any_pdf:
            messagebox.showerror("No PDFs", "You removed all PDFs. Select at least one.")
            return

        default_out = self.folder / "combined_labs.pdf"
        out_path = filedialog.asksaveasfilename(
            title="Save combined PDF as...",
            initialdir=str(self.folder),
            initialfile=default_out.name,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not out_path:
            return

        output_pdf = Path(out_path)

        try:
            combine_with_movable_toc_and_numbers(
                self.items,
                output_pdf,
                toc_title="Table of Contents",
                page_num_alignment=self.page_num_alignment.get() or "center",
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to combine PDFs:\n\n{e}")
            return

        messagebox.showinfo("Done", f"Created:\n{output_pdf}")


def main() -> None:
    root = tk.Tk()

    folder_selected = filedialog.askdirectory(title="Select folder containing PDF lab sheets")
    if not folder_selected:
        root.destroy()
        return

    folder = Path(folder_selected)
    pdfs = gather_pdfs_in_folder(folder)

    if not pdfs:
        messagebox.showerror("No PDFs Found", f"No PDF files were found in:\n{folder}")
        root.destroy()
        return

    PdfOrderApp(root, folder, pdfs)
    root.mainloop()


if __name__ == "__main__":
    main()
