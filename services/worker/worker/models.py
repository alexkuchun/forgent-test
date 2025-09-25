from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Requirement(BaseModel):
    id: str
    page_refs: List[int] = Field(default_factory=list)
    text: str
    category: str  # submission|eligibility|technical|financial|other
    is_mandatory: bool
    deadline: Optional[str] = None
    submission_format: Optional[str] = None
    source_quote: Optional[str] = None

class ExtractResponse(BaseModel):
    requirements: List[Requirement] = Field(default_factory=list)

class ChecklistItem(BaseModel):
    id: str
    title: str
    description: str
    category: str
    is_mandatory: bool
    due_date: Optional[str] = None
    status: str = "open"
    page_refs: List[int] = Field(default_factory=list)
    evidence_required: Optional[bool] = None

class Checklist(BaseModel):
    items: List[ChecklistItem] = Field(default_factory=list)


class Prompt(BaseModel):
    id: int
    prompt_text: str
    prompt_type: Literal["QUESTION", "CONDITION"]


class PromptResult(BaseModel):
    prompt_id: int
    prompt_type: Literal["QUESTION", "CONDITION"]
    answer_text: Optional[str] = None
    boolean_result: Optional[bool] = None
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    page_refs: List[int] = Field(default_factory=list)
    status: str = "READY"
    error: Optional[str] = None
