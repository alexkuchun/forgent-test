from __future__ import annotations
from typing import List, Dict, Any


def chunk_pages(pages: List[Dict[str, Any]], window: int, overlap: int) -> List[Dict[str, Any]]:
    """Create sliding window chunks from pages.

    Each page dict must have {"page_no": int, "text": str}.
    Returns a list of chunks: {chunk_id, page_start, page_end, text}
    where text is the concatenation of page texts with markers.
    """
    if window <= 0:
        raise ValueError("window must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")

    chunks: List[Dict[str, Any]] = []
    n = len(pages)
    if n == 0:
        return chunks

    i = 0
    cid = 1
    while i < n:
        j = min(i + window, n)
        group = pages[i:j]
        page_start = group[0]["page_no"]
        page_end = group[-1]["page_no"]
        text = "\n\n".join([f"[Page {p['page_no']}]\n{p['text']}" for p in group])
        chunks.append({
            "chunk_id": cid,
            "page_start": page_start,
            "page_end": page_end,
            "text": text,
        })
        cid += 1
        if j == n:
            break
        i = max(0, j - overlap)
    return chunks
