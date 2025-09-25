from __future__ import annotations
from typing import List
from .models import Requirement
from .embeddings import similarity
from .config import get_settings


def dedupe_requirements(reqs: List[Requirement]) -> List[Requirement]:
    if not reqs:
        return []
    s = get_settings()
    threshold = s.similarity_threshold
    keep: List[Requirement] = []

    for req in reqs:
        duplicate_found = False
        for existing in keep:
            sim = similarity(req.text, existing.text)
            if sim >= threshold:
                duplicate_found = True
                merged_pages = sorted(set(existing.page_refs + req.page_refs))
                existing.page_refs = merged_pages
                break
        if not duplicate_found:
            keep.append(req)
    return keep


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().replace("•", "").split())
