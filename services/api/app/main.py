import os
import uuid
from typing import List

from app.db import Base, engine, get_db
from app.jobs import process_checklist_sync
from app.models import Checklist, ChecklistStatus, Document, ChecklistItem, ChecklistItemPriority, PromptTemplate, ChecklistPrompt, PromptType
from app.schemas import (
    ChecklistCreate,
    ChecklistDetailOut,
    ChecklistListItem,
    ChecklistOut,
    DocumentOut,
    DocumentUploadIn,
    ChecklistItemOut,
    ChecklistItemPatch,
    PromptTemplateIn,
    PromptTemplateUpdate,
    PromptTemplateOut,
    ChecklistPromptIn,
    ChecklistPromptUpdate,
    ChecklistPromptOut,
    WorkerChecklistIn,
    WorkerPromptResultIn,
    WorkerStatusIn,
)
from app.storage import upload_pdf_from_base64
from app.queue import broker_available, enqueue_process_tender
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

load_dotenv()
app = FastAPI(title="Forgent Checklist API", version="0.1.0")

# CORS for local dev (adjust in prod)
# Build allowed origins from env, keeping localhost defaults.
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if _env_origins.strip():
    _allowed_origins.extend([o.strip() for o in _env_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _create_tables():
    # For the MVP, create tables automatically. Replace with Alembic later if desired.
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"ok": True}

# TODO: Implement endpoints mirroring the original API
# - GET /api/checklists
# - POST /api/checklists
# - GET /api/checklists/{id}
# - POST /api/checklists/{id}/upload
# - POST /api/checklists/{id}/process
# - GET /api/checklists/{id}/items
# - PATCH /api/checklist-items/{id}

# --- Dev-mode processing toggle ---
# If LOCAL_SYNC_PROCESSOR=1 (default), run the processing pipeline synchronously
# via a FastAPI BackgroundTask, avoiding the need for a local Redis.
# In production on Railway, set LOCAL_SYNC_PROCESSOR=0 and enqueue to a broker instead.
LOCAL_SYNC_PROCESSOR = os.getenv("LOCAL_SYNC_PROCESSOR", "1") == "1"
WORKER_INGEST_TOKEN = os.getenv("WORKER_INGEST_TOKEN")


def _prompt_template_to_out(template: PromptTemplate) -> PromptTemplateOut:
    return PromptTemplateOut(
        id=template.id,
        title=template.title,
        prompt_text=template.prompt_text,
        prompt_type=template.prompt_type.value,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _checklist_prompt_to_out(prompt: ChecklistPrompt) -> ChecklistPromptOut:
    return ChecklistPromptOut(
        id=prompt.id,
        checklist_id=prompt.checklist_id,
        prompt_text=prompt.prompt_text,
        prompt_type=prompt.prompt_type.value,
        answer_text=prompt.answer_text,
        boolean_result=prompt.boolean_result,
        confidence=prompt.confidence,
        evidence=prompt.evidence,
        page_refs=prompt.page_refs or [],
        status=prompt.status,
        error=prompt.error,
        template_id=prompt.template_id,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


def _coerce_prompt_type(value: str | PromptType) -> PromptType:
    if isinstance(value, PromptType):
        return value
    try:
        return PromptType(value.upper())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prompt_type")


def _verify_worker_token(header: str | None):
    if not WORKER_INGEST_TOKEN:
        raise HTTPException(status_code=503, detail="Worker ingest token not configured")
    if not header or not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing worker authorization")
    provided = header.split(" ", 1)[1].strip()
    if provided != WORKER_INGEST_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid worker authorization")


@app.post("/api/checklists/{checklist_id}/process")
def process_checklist_endpoint(
    checklist_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if LOCAL_SYNC_PROCESSOR:
        # Kick off processing in the background and return immediately
        background_tasks.add_task(process_checklist_sync, checklist_id)
        return {
            "success": True,
            "workflowId": "local-sync",
            "message": "Processing started (local sync mode)",
        }
    if not broker_available():
        raise HTTPException(status_code=503, detail="Queue not configured; set REDIS_URL")

    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    docs = (
        db.query(Document)
        .filter(Document.checklist_id == checklist_id)
        .order_by(Document.created_at.asc())
        .all()
    )
    if not docs:
        raise HTTPException(status_code=400, detail="Checklist has no documents to process")

    checklist.status = ChecklistStatus.PROCESSING
    db.add(checklist)
    db.commit()

    job_id = f"{checklist_id}-{uuid.uuid4().hex[:6]}"
    payload = {
        "job_id": job_id,
        "checklist_id": checklist_id,
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "storage_key": d.storage_key,
            }
            for d in docs
        ],
        "options": {},
    }
    enqueue_process_tender(payload)
    return {
        "success": True,
        "workflowId": "queue",
        "message": "Processing enqueued",
        "jobId": job_id,
    }


# ---------- Checklist Endpoints ----------

@app.post("/api/checklists", response_model=ChecklistOut)
@app.post("/api/checklists/", response_model=ChecklistOut)
def create_checklist(payload: ChecklistCreate, db: Session = Depends(get_db)):
    cid = uuid.uuid4().hex[:12]
    title = payload.title or "Untitled Checklist"
    checklist = Checklist(id=cid, title=title, status=ChecklistStatus.DRAFT)
    db.add(checklist)
    db.commit()
    db.refresh(checklist)

    # Seed default prompts from templates flagged as default
    defaults = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.is_default.is_(True))
        .order_by(PromptTemplate.created_at.asc())
        .all()
    )
    for tpl in defaults:
        prompt = ChecklistPrompt(
            checklist_id=checklist.id,
            template_id=tpl.id,
            prompt_text=tpl.prompt_text,
            prompt_type=tpl.prompt_type,
            status="PENDING",
        )
        db.add(prompt)
    if defaults:
        db.commit()

    return ChecklistOut(
        id=checklist.id,
        title=checklist.title,
        status=checklist.status.value if hasattr(checklist.status, "value") else str(checklist.status),
        meta=checklist.meta,
        created_at=checklist.created_at,
        updated_at=checklist.updated_at,
    )


@app.get("/api/checklists", response_model=List[ChecklistListItem])
def list_checklists(db: Session = Depends(get_db)):
    counts_subq = (
        db.query(Document.checklist_id, func.count(Document.id).label("cnt"))
        .group_by(Document.checklist_id)
        .subquery()
    )
    rows = (
        db.query(
            Checklist,
            func.coalesce(counts_subq.c.cnt, 0),
        )
        .outerjoin(counts_subq, Checklist.id == counts_subq.c.checklist_id)
        .order_by(Checklist.created_at.desc())
        .all()
    )
    out: List[ChecklistListItem] = []
    for chk, cnt in rows:
        out.append(
            ChecklistListItem(
                id=chk.id,
                title=chk.title,
                status=chk.status.value if hasattr(chk.status, "value") else str(chk.status),
                created_at=chk.created_at,
                updated_at=chk.updated_at,
                document_count=int(cnt or 0),
            )
        )
    return out


@app.get("/api/checklists/{checklist_id}", response_model=ChecklistDetailOut)
def get_checklist(checklist_id: str, db: Session = Depends(get_db)):
    chk = db.get(Checklist, checklist_id)
    if not chk:
        raise HTTPException(status_code=404, detail="Checklist not found")

    docs = (
        db.query(Document)
        .filter(Document.checklist_id == checklist_id)
        .order_by(Document.created_at.asc())
        .all()
    )
    items = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist_id)
        .order_by(ChecklistItem.order_index.asc(), ChecklistItem.id.asc())
        .all()
    )
    prompts = (
        db.query(ChecklistPrompt)
        .filter(ChecklistPrompt.checklist_id == checklist_id)
        .order_by(ChecklistPrompt.created_at.asc())
        .all()
    )
    return ChecklistDetailOut(
        id=chk.id,
        title=chk.title,
        status=chk.status.value if hasattr(chk.status, "value") else str(chk.status),
        meta=chk.meta,
        created_at=chk.created_at,
        updated_at=chk.updated_at,
        documents=[
            DocumentOut(
                id=d.id,
                filename=d.filename,
                storage_key=d.storage_key,
                content_type=d.content_type,
                size_bytes=d.size_bytes,
                created_at=d.created_at,
            )
            for d in docs
        ],
        items=[
            ChecklistItemOut(
                id=i.id,
                text=i.text,
                category=i.category,
                priority=i.priority.value if getattr(i.priority, "value", None) is not None else (str(i.priority) if i.priority else None),
                order_index=i.order_index,
                completed=bool(i.completed),
            )
            for i in items
        ],
        prompts=[_checklist_prompt_to_out(p) for p in prompts],
    )


@app.delete("/api/checklists/{checklist_id}")
def delete_checklist(checklist_id: str, db: Session = Depends(get_db)):
    chk = db.get(Checklist, checklist_id)
    if not chk:
        raise HTTPException(status_code=404, detail="Checklist not found")
    # ORM-level cascade will delete related documents/items per relationship config
    db.delete(chk)
    db.commit()
    return {"success": True}


@app.post("/api/checklists/{checklist_id}/upload", response_model=DocumentOut)
def upload_document(checklist_id: str, body: DocumentUploadIn, db: Session = Depends(get_db)):
    chk = db.get(Checklist, checklist_id)
    if not chk:
        raise HTTPException(status_code=404, detail="Checklist not found")

    # Simple status transition: mark as UPLOADING if currently DRAFT
    original_status = chk.status
    if chk.status == ChecklistStatus.DRAFT:
        chk.status = ChecklistStatus.UPLOADING
        db.add(chk)
        db.commit()
        db.refresh(chk)

    # Upload to S3
    storage_key, size_bytes = upload_pdf_from_base64(
        checklist_id=checklist_id,
        filename=body.filename,
        base64_data=body.base64,
        content_type=body.content_type or "application/pdf",
    )

    # Create document row
    doc = Document(
        checklist_id=checklist_id,
        filename=body.filename,
        storage_key=storage_key,
        content_type=body.content_type or "application/pdf",
        size_bytes=size_bytes,
    )
    db.add(doc)

    # Restore status to DRAFT if we set it to UPLOADING
    if original_status == ChecklistStatus.DRAFT:
        chk.status = ChecklistStatus.DRAFT
        db.add(chk)

    db.commit()
    db.refresh(doc)

    return DocumentOut(
        id=doc.id,
        filename=doc.filename,
        storage_key=doc.storage_key,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
    )


@app.post("/api/internal/checklists/{checklist_id}/ingest")
def ingest_checklist(
    checklist_id: str,
    payload: WorkerChecklistIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_worker_token(authorization)
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    # Replace existing items
    db.query(ChecklistItem).filter(ChecklistItem.checklist_id == checklist_id).delete()

    for idx, item in enumerate(payload.items, start=1):
        text = item.description or item.title
        checklist_item = ChecklistItem(
            checklist_id=checklist_id,
            text=text,
            category=item.category,
            order_index=idx,
            completed=0,
        )
        db.add(checklist_item)

    # Update prompt results
    prompt_results = payload.prompts or []
    updated_prompt_ids = set()
    for res in prompt_results:
        prompt = db.get(ChecklistPrompt, res.prompt_id)
        if not prompt or prompt.checklist_id != checklist_id:
            continue
        prompt.answer_text = res.answer_text
        prompt.boolean_result = res.boolean_result
        prompt.confidence = res.confidence
        prompt.evidence = res.evidence
        prompt.page_refs = res.page_refs or []
        prompt.error = res.error
        if res.status:
            prompt.status = res.status
        else:
            prompt.status = "FAILED" if res.error else "READY"
        db.add(prompt)
        updated_prompt_ids.add(prompt.id)

    # Any prompts not included remain pending unless already marked otherwise
    remaining_prompts = (
        db.query(ChecklistPrompt)
        .filter(ChecklistPrompt.checklist_id == checklist_id)
        .all()
    )
    for prompt in remaining_prompts:
        if prompt.id not in updated_prompt_ids and prompt.status == "PROCESSING":
            prompt.status = "PENDING"
            db.add(prompt)

    checklist.status = ChecklistStatus.READY
    meta = checklist.meta or {}
    if payload.meta:
        meta["worker"] = payload.meta
    if prompt_results:
        meta["workerPromptsProcessed"] = len(prompt_results)
    checklist.meta = meta
    db.add(checklist)
    db.commit()
    return {"success": True, "items": len(payload.items)}


@app.post("/api/internal/checklists/{checklist_id}/status")
def update_status(
    checklist_id: str,
    payload: WorkerStatusIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_worker_token(authorization)
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    status_value = payload.status.upper()
    try:
        checklist.status = ChecklistStatus(status_value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status value")

    if payload.error:
        meta = checklist.meta or {}
        meta["workerError"] = payload.error
        checklist.meta = meta

    db.delete(chk)
    db.commit()
    return {"success": True}


# ---------- Prompt Template Endpoints ----------


@app.get("/api/prompt-templates", response_model=List[PromptTemplateOut])
def list_prompt_templates(db: Session = Depends(get_db)):
    rows = db.query(PromptTemplate).order_by(PromptTemplate.created_at.asc()).all()
    return [_prompt_template_to_out(tpl) for tpl in rows]


@app.post("/api/prompt-templates", response_model=PromptTemplateOut)
def create_prompt_template(payload: PromptTemplateIn, db: Session = Depends(get_db)):
    prompt_type = _coerce_prompt_type(payload.prompt_type)
    tpl = PromptTemplate(
        title=payload.title,
        prompt_text=payload.prompt_text,
        prompt_type=prompt_type,
        is_default=payload.is_default,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return _prompt_template_to_out(tpl)


@app.patch("/api/prompt-templates/{template_id}", response_model=PromptTemplateOut)
def update_prompt_template(template_id: int, payload: PromptTemplateUpdate, db: Session = Depends(get_db)):
    tpl = db.get(PromptTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if payload.title is not None:
        tpl.title = payload.title
    if payload.prompt_text is not None:
        tpl.prompt_text = payload.prompt_text
    if payload.prompt_type is not None:
        tpl.prompt_type = _coerce_prompt_type(payload.prompt_type)
    if payload.is_default is not None:
        tpl.is_default = payload.is_default
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return _prompt_template_to_out(tpl)


@app.delete("/api/prompt-templates/{template_id}")
def delete_prompt_template(template_id: int, db: Session = Depends(get_db)):
    tpl = db.get(PromptTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    db.delete(tpl)
    db.commit()
    return {"success": True}


# ---------- Checklist Prompt Endpoints ----------


@app.get("/api/checklists/{checklist_id}/prompts", response_model=List[ChecklistPromptOut])
def list_checklist_prompts(checklist_id: str, db: Session = Depends(get_db)):
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    prompts = (
        db.query(ChecklistPrompt)
        .filter(ChecklistPrompt.checklist_id == checklist_id)
        .order_by(ChecklistPrompt.created_at.asc())
        .all()
    )
    return [_checklist_prompt_to_out(p) for p in prompts]


@app.post("/api/checklists/{checklist_id}/prompts", response_model=ChecklistPromptOut)
def create_checklist_prompt(
    checklist_id: str,
    payload: ChecklistPromptIn,
    db: Session = Depends(get_db),
):
    checklist = db.get(Checklist, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")

    prompt_text = payload.prompt_text
    prompt_type: PromptType | None = _coerce_prompt_type(payload.prompt_type) if payload.prompt_type else None
    template_id = payload.template_id

    if template_id:
        tpl = db.get(PromptTemplate, template_id)
        if not tpl:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        if prompt_text is None:
            prompt_text = tpl.prompt_text
        if prompt_type is None:
            prompt_type = tpl.prompt_type
    if not prompt_text or not prompt_type:
        raise HTTPException(status_code=400, detail="prompt_text and prompt_type are required")

    prompt = ChecklistPrompt(
        checklist_id=checklist_id,
        template_id=template_id,
        prompt_text=prompt_text,
        prompt_type=prompt_type,
        status="PENDING",
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return _checklist_prompt_to_out(prompt)


@app.patch("/api/checklists/{checklist_id}/prompts/{prompt_id}", response_model=ChecklistPromptOut)
def update_checklist_prompt(
    checklist_id: str,
    prompt_id: int,
    payload: ChecklistPromptUpdate,
    db: Session = Depends(get_db),
):
    prompt = (
        db.query(ChecklistPrompt)
        .filter(ChecklistPrompt.id == prompt_id, ChecklistPrompt.checklist_id == checklist_id)
        .first()
    )
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if payload.prompt_text is not None:
        prompt.prompt_text = payload.prompt_text
    if payload.prompt_type is not None:
        prompt.prompt_type = _coerce_prompt_type(payload.prompt_type)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return _checklist_prompt_to_out(prompt)


@app.delete("/api/checklists/{checklist_id}/prompts/{prompt_id}")
def delete_checklist_prompt(checklist_id: str, prompt_id: int, db: Session = Depends(get_db)):
    prompt = (
        db.query(ChecklistPrompt)
        .filter(ChecklistPrompt.id == prompt_id, ChecklistPrompt.checklist_id == checklist_id)
        .first()
    )
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(prompt)
    db.commit()
    return {"success": True}


# ---------- Checklist Endpoints ----------


@app.get("/api/checklists/{checklist_id}/items", response_model=List[ChecklistItemOut])
def list_checklist_items(checklist_id: str, db: Session = Depends(get_db)):
    chk = db.get(Checklist, checklist_id)
    if not chk:
        raise HTTPException(status_code=404, detail="Checklist not found")
    rows = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist_id)
        .order_by(ChecklistItem.order_index.asc(), ChecklistItem.id.asc())
        .all()
    )
    return [
        ChecklistItemOut(
            id=r.id,
            text=r.text,
            category=r.category,
            priority=r.priority.value if getattr(r.priority, "value", None) is not None else (str(r.priority) if r.priority else None),
            order_index=r.order_index,
            completed=bool(r.completed),
        )
        for r in rows
    ]


@app.patch("/api/checklist-items/{item_id}", response_model=ChecklistItemOut)
def patch_checklist_item(item_id: int, body: ChecklistItemPatch, db: Session = Depends(get_db)):
    item = db.get(ChecklistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    if body.text is not None:
        item.text = body.text
    if body.category is not None:
        item.category = body.category
    if body.priority is not None:
        try:
            item.priority = ChecklistItemPriority(body.priority.upper())
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid priority; use LOW, MEDIUM, or HIGH")
    if body.order_index is not None:
        item.order_index = body.order_index
    if body.completed is not None:
        item.completed = 1 if body.completed else 0

    db.add(item)
    db.commit()
    db.refresh(item)

    return ChecklistItemOut(
        id=item.id,
        text=item.text,
        category=item.category,
        priority=item.priority.value if getattr(item.priority, "value", None) is not None else (str(item.priority) if item.priority else None),
        order_index=item.order_index,
        completed=bool(item.completed),
    )
