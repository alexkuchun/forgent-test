from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class ChecklistCreate(BaseModel):
    title: Optional[str] = Field(default=None)


class ChecklistListItem(BaseModel):
    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    document_count: int


class DocumentOut(BaseModel):
    id: int
    filename: str
    storage_key: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: datetime


class DocumentUploadIn(BaseModel):
    filename: str
    base64: str
    content_type: Optional[str] = None


class ChecklistOut(BaseModel):
    id: str
    title: str
    status: str
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ChecklistDetailOut(ChecklistOut):
    documents: List[DocumentOut] = Field(default_factory=list)
    items: List[ChecklistItemOut] = Field(default_factory=list)
    prompts: List[ChecklistPromptOut] = Field(default_factory=list)


class ChecklistItemOut(BaseModel):
    id: int
    text: str
    category: Optional[str] = None
    priority: Optional[str] = None
    order_index: Optional[int] = None
    completed: bool


class ChecklistItemPatch(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None  # one of LOW, MEDIUM, HIGH
    order_index: Optional[int] = None
    completed: Optional[bool] = None


class PromptTemplateIn(BaseModel):
    title: str
    prompt_text: str
    prompt_type: Literal["QUESTION", "CONDITION"]
    is_default: bool = False


class PromptTemplateUpdate(BaseModel):
    title: Optional[str] = None
    prompt_text: Optional[str] = None
    prompt_type: Optional[Literal["QUESTION", "CONDITION"]] = None
    is_default: Optional[bool] = None


class PromptTemplateOut(BaseModel):
    id: int
    title: str
    prompt_text: str
    prompt_type: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ChecklistPromptIn(BaseModel):
    prompt_text: Optional[str] = None
    prompt_type: Optional[Literal["QUESTION", "CONDITION"]] = None
    template_id: Optional[int] = None


class ChecklistPromptUpdate(BaseModel):
    prompt_text: Optional[str] = None
    prompt_type: Optional[Literal["QUESTION", "CONDITION"]] = None


class ChecklistPromptOut(BaseModel):
    id: int
    checklist_id: str
    prompt_text: str
    prompt_type: str
    answer_text: Optional[str] = None
    boolean_result: Optional[bool] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    page_refs: List[int] = Field(default_factory=list)
    status: str
    error: Optional[str] = None
    template_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class WorkerChecklistItemIn(BaseModel):
    id: str
    title: str
    description: str
    category: Optional[str] = None
    is_mandatory: bool = False
    due_date: Optional[str] = None
    status: Optional[str] = None
    page_refs: List[int] = Field(default_factory=list)
    evidence_required: Optional[bool] = None


class WorkerChecklistIn(BaseModel):
    items: List[WorkerChecklistItemIn] = Field(default_factory=list)
    meta: Optional[dict] = None
    prompts: List[WorkerPromptResultIn] = Field(default_factory=list)


class WorkerPromptResultIn(BaseModel):
    prompt_id: int
    prompt_type: Literal["QUESTION", "CONDITION"]
    answer_text: Optional[str] = None
    boolean_result: Optional[bool] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    page_refs: List[int] = Field(default_factory=list)
    error: Optional[str] = None
    status: Optional[str] = None


class WorkerStatusIn(BaseModel):
    status: str
    error: Optional[str] = None
