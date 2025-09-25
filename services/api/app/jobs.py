import time
import logging

logger = logging.getLogger(__name__)
from typing import List
import os
import base64
from anthropic import Anthropic
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import SessionLocal
from .models import Checklist, Document, ChecklistItem, ChecklistStatus
from .storage import download_bytes


def process_checklist_sync(checklist_id: str) -> None:
    """Real processing pipeline using S3 + Anthropic.

    Steps:
      1) Mark checklist as PROCESSING
      2) Download PDFs from S3
      3) OCR each PDF with Anthropic (PDF attachment)
      4) Combine text and ask Claude to emit a simple bullet list of actions
      5) Persist items and mark checklist READY; on error mark FAILED
    """
    logger.info("[jobs] start process_checklist_sync checklist_id=%s", checklist_id)
    start_ts = time.time()

    db: Session = SessionLocal()
    try:
        chk = db.get(Checklist, checklist_id)
        if not chk:
            logger.error("[jobs] checklist not found: %s", checklist_id)
            return

        chk.status = ChecklistStatus.PROCESSING
        db.add(chk)
        db.commit()

        docs: List[Document] = db.scalars(
            select(Document).where(Document.checklist_id == checklist_id).order_by(Document.created_at.asc())
        ).all()
        if not docs:
            chk.status = ChecklistStatus.FAILED
            chk.meta = {"error": "No documents to process"}
            db.add(chk)
            db.commit()
            logger.error("[jobs] no documents for checklist %s", checklist_id)
            return

        # Prepare Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        client = Anthropic(api_key=api_key)

        # 1) OCR all PDFs
        combined_text_parts: List[str] = []
        for d in docs:
            pdf_bytes = download_bytes(d.storage_key)
            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
            logger.info("[jobs] OCR via Claude for document id=%s size=%sB", d.id, len(pdf_bytes))
            ocr_start = time.time()
            msg = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=4000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extract all readable text from this PDF. Return only plain text without commentary."
                                ),
                            },
                        ],
                    }
                ],
            )
            ocr_text = "".join([block.text for block in msg.content if getattr(block, "type", None) == "text"]) or ""
            d.ocr_results = {
                "text": ocr_text[:200000],  # guard against extremely long text
                "processingTime": round(time.time() - ocr_start, 3),
            }
            db.add(d)
            combined_text_parts.append(ocr_text)
            db.commit()

        combined_text = "\n\n".join(combined_text_parts)

        # 2) Generate a simple checklist as bullet points
        gen_prompt = (
            "You are a helpful assistant that turns long documents into a short actionable checklist. "
            "From the given text, produce 8-20 concise action items. "
            "Return one item per line starting with '- '. Do not include any other prose."
        )
        msg2 = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": gen_prompt},
                        {"type": "text", "text": combined_text[:150000]},
                    ],
                }
            ],
        )
        raw = "".join([block.text for block in msg2.content if getattr(block, "type", None) == "text"]) or ""
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        items = []
        for ln in lines:
            if ln.startswith("- "):
                items.append(ln[2:].strip())
            else:
                items.append(ln)

        # 3) Persist items
        # Clear previous items (if any) and insert new ones in order
        # For MVP, we just append; to replace, you'd delete then insert.
        for idx, txt in enumerate(items[:100], start=1):
            db.add(ChecklistItem(checklist_id=checklist_id, text=txt, order_index=idx))
        chk.status = ChecklistStatus.READY
        if not chk.title or chk.title == "Untitled Checklist":
            chk.title = f"Checklist for {checklist_id}"
        chk.meta = {
            "generatedItemCount": len(items),
            "processingSeconds": round(time.time() - start_ts, 3),
        }
        db.add(chk)
        db.commit()
        logger.info("[jobs] finished process_checklist_sync checklist_id=%s items=%s", checklist_id, len(items))
    except Exception as e:
        logger.exception("[jobs] processing failed for %s: %s", checklist_id, e)
        try:
            chk = db.get(Checklist, checklist_id)
            if chk:
                chk.status = ChecklistStatus.FAILED
                chk.meta = {"error": str(e)}
                db.add(chk)
                db.commit()
        except Exception:
            logger.exception("[jobs] failed to mark checklist %s as FAILED", checklist_id)
    finally:
        db.close()
