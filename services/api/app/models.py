from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Boolean,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
import enum


class ChecklistStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class PromptType(str, enum.Enum):
    QUESTION = "QUESTION"
    CONDITION = "CONDITION"


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled Checklist")
    status: Mapped[ChecklistStatus] = mapped_column(Enum(ChecklistStatus), default=ChecklistStatus.DRAFT)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow)

    documents: Mapped[list[Document]] = relationship("Document", back_populates="checklist", cascade="all, delete-orphan")
    items: Mapped[list[ChecklistItem]] = relationship("ChecklistItem", back_populates="checklist", cascade="all, delete-orphan")
    prompts: Mapped[list[ChecklistPrompt]] = relationship("ChecklistPrompt", back_populates="checklist", cascade="all, delete-orphan")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    prompt_text: Mapped[str] = mapped_column(Text)
    prompt_type: Mapped[PromptType] = mapped_column(Enum(PromptType))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow)

    checklist_prompts: Mapped[list[ChecklistPrompt]] = relationship("ChecklistPrompt", back_populates="template")


class ChecklistPrompt(Base):
    __tablename__ = "checklist_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checklist_id: Mapped[str] = mapped_column(String(64), ForeignKey("checklists.id", ondelete="CASCADE"))
    template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True)
    prompt_text: Mapped[str] = mapped_column(Text)
    prompt_type: Mapped[PromptType] = mapped_column(Enum(PromptType))
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    boolean_result: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_refs: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow)

    checklist: Mapped[Checklist] = relationship("Checklist", back_populates="prompts")
    template: Mapped[PromptTemplate | None] = relationship("PromptTemplate", back_populates="checklist_prompts")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checklist_id: Mapped[str] = mapped_column(String(64), ForeignKey("checklists.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ocr_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    checklist: Mapped[Checklist] = relationship("Checklist", back_populates="documents")


class ChecklistItemPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checklist_id: Mapped[str] = mapped_column(String(64), ForeignKey("checklists.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    priority: Mapped[Optional[ChecklistItemPriority]] = mapped_column(Enum(ChecklistItemPriority), nullable=True)
    order_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed: Mapped[bool] = mapped_column(Integer, default=0)  # 0/1 boolean

    checklist: Mapped[Checklist] = relationship("Checklist", back_populates="items")
