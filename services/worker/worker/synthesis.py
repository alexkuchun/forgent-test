from __future__ import annotations
import re
from typing import List
from uuid import uuid4
from datetime import datetime
from .models import Requirement, Checklist, ChecklistItem

DATE_PATTERNS = [
    r"(\d{4}-\d{2}-\d{2})",
    r"(\d{2}/\d{2}/\d{4})",
    r"(\d{2}-\d{2}-\d{4})",
    r"(\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
]

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def synthesize_checklist(requirements: List[Requirement]) -> Checklist:
    items: List[ChecklistItem] = []
    for idx, req in enumerate(requirements, start=1):
        title = derive_title(req.text)
        due_date = derive_due_date(req)
        item = ChecklistItem(
            id=req.id or uuid4().hex,
            title=title,
            description=req.text,
            category=req.category,
            is_mandatory=req.is_mandatory,
            due_date=due_date,
            status="open",
            page_refs=req.page_refs,
            evidence_required=None,
        )
        items.append(item)
    return Checklist(items=items)


def derive_title(text: str) -> str:
    words = [w.strip(" ,.;:") for w in text.split() if w.strip()]
    if not words:
        return "Untitled requirement"
    snippet = " ".join(words[: min(len(words), 12)])
    return snippet[0].upper() + snippet[1:]


def derive_due_date(req: Requirement) -> str | None:
    text = req.deadline or req.text
    if not text:
        return None
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1)
            iso = normalize_date(value)
            if iso:
                return iso
    return None


def normalize_date(value: str) -> str | None:
    value = value.strip()
    try:
        if re.match(r"\d{4}-\d{2}-\d{2}$", value):
            datetime.strptime(value, "%Y-%m-%d")
            return value
        if re.match(r"\d{2}/\d{2}/\d{4}$", value):
            dt = datetime.strptime(value, "%m/%d/%Y")
            return dt.strftime("%Y-%m-%d")
        if re.match(r"\d{2}-\d{2}-\d{4}$", value):
            dt = datetime.strptime(value, "%m-%d-%Y")
            return dt.strftime("%Y-%m-%d")
        month_match = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", value)
        if month_match:
            day = int(month_match.group(1))
            month_name = month_match.group(2).lower()
            year = int(month_match.group(3))
            month = MONTHS.get(month_name)
            if month:
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None
