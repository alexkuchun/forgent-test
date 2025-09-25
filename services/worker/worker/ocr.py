from __future__ import annotations
from typing import List, Dict, Any
import fitz  # PyMuPDF


def extract_pages_text(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """Return a list of {page_no, text} objects using PyMuPDF."""
    pages: List[Dict[str, Any]] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            try:
                text = page.get_text("text") or ""
            except Exception:
                text = ""
            pages.append({"page_no": i, "text": text})
    return pages
