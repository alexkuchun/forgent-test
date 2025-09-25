# Tender Document Processing Worker (MVP)

This file contains the **complete specification** for a background worker that processes procurement/tender documents into structured checklists.  
It merges workflow design, implementation details, data schemas, prompts, and examples into one place. You can hand this file to another coding LLM and ask it to implement the worker accordingly.

---

## 0. Scope

- **API and web interface are already implemented.**
- This specification covers **only the worker**:
  - Queue messages & orchestration (Dramatiq + Redis).
  - Document preprocessing (PDF/OCR → text).
  - Chunking with overlap.
  - Requirement extraction using LLM (Gemini 2.5 Flash / Pro).
  - JSON validation and repair.
  - Deduplication using embeddings.
  - Checklist synthesis.
  - Persistence in S3-compatible storage.

---

## 1. High-Level Workflow

### Entry point

- API pushes a job into the queue:
  ```
  process_tender(job_id, file_url, filename)
  ```
- Worker processes in multiple steps and persists artifacts.

### Processing Steps

1. **Preflight**

   - Detect file type (PDF/DOCX/Image).
   - Extract text per page:
     - PDF with text layer → use PyMuPDF.
     - Scanned/bitmap → use Google Vision OCR.
   - Save:
     - `/jobs/{job_id}/raw.pdf`
     - `/jobs/{job_id}/pages.json` → `{page_no, text}`

2. **Chunking**

   - Sliding windows: **5 pages with 1-page overlap**.
   - Example: [1–5], [5–9], [9–13].
   - Save: `/jobs/{job_id}/chunks/{chunk_id}.json`.
   - Enqueue `extract_chunk` per chunk.

3. **Requirement Extraction (LLM)**

   - Call **Gemini 2.5 Flash** (primary).
   - Fallback: **Gemini 2.5 Pro** if invalid JSON or ambiguous.
   - Strict JSON schema enforced (see Section 3).
   - Retry 2× with exponential backoff on timeout.
   - If invalid JSON → enqueue `repair_json`.

4. **Repair JSON**

   - Minimal prompt to reformat into valid JSON.
   - Validate again.
   - If still invalid → fallback to Gemini 2.5 Pro.
   - Save repaired JSON.

5. **Merge & Deduplicate**

   - Aggregate requirements from all chunks.
   - Normalize text (lowercase, trim whitespace, remove bullets).
   - Compute embeddings (`text-embedding-004`).
   - Cosine similarity ≥ 0.95 → mark as duplicates.
   - Keep first occurrence, merge `page_refs`.

6. **Checklist Synthesis**

   - Convert requirements → checklist items.
   - Add:
     - `title`: short summary (first 8–12 words or LLM paraphrase).
     - `due_date`: parsed via regex → ISO date; fallback to LLM for free-form.
     - `page_refs` and `source_quote`.
   - Save: `/jobs/{job_id}/checklist.json`.

7. **Completion Signal**
   - Write `/jobs/{job_id}/status.json` with:
     ```json
     { "status": "done", "items": 37 }
     ```

---

## 2. Message Contracts

### `process_tender`

```json
{
  "job_id": "uuid",
  "file_url": "s3 or https url",
  "filename": "original.pdf",
  "options": {
    "chunk_window_pages": 5,
    "chunk_overlap_pages": 1,
    "embedding_threshold": 0.95
  }
}
```

### `extract_chunk`

```json
{
  "job_id": "uuid",
  "chunk_id": "uuid",
  "page_start": 1,
  "page_end": 5,
  "text": "string"
}
```

### `repair_json`

```json
{
  "job_id": "uuid",
  "chunk_id": "uuid",
  "raw_response": "string"
}
```

---

## 3. Data Models (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

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
```

---

## 4. JSON Schemas

### Extraction Schema

```json
{
  "requirements": [
    {
      "id": "string",
      "page_refs": [0],
      "text": "string",
      "category": "submission|eligibility|technical|financial|other",
      "is_mandatory": true,
      "deadline": "YYYY-MM-DD|null",
      "submission_format": "string|null",
      "source_quote": "string"
    }
  ]
}
```

### Checklist Schema

```json
{
  "items": [
    {
      "id": "string",
      "title": "string",
      "description": "string",
      "category": "submission|eligibility|technical|financial|other",
      "is_mandatory": true,
      "due_date": "YYYY-MM-DD|null",
      "status": "open",
      "page_refs": [0],
      "evidence_required": true
    }
  ]
}
```

---

## 5. Prompts

### `extract_system.txt`

```
You extract explicit procurement requirements from tender documents.
Return STRICT JSON compliant with the provided schema.
Do not invent information. If no requirements are present in this chunk, return {"requirements": []}.
Do not include any additional text outside JSON.
```

### `extract_user.txt`

```
Document pages: {page_start}-{page_end}
Schema: { ... see Extraction Schema ... }

Extract only explicit requirements with page references from this chunk:
---
{chunk_text}
---
```

### `repair_system.txt`

```
You repair invalid JSON. Output ONLY valid JSON that conforms to the schema. Do not add explanations.
```

---

## 6. Deduplication Strategy

- Generate embeddings for each requirement `text` using `text-embedding-004`.
- Compute cosine similarity between pairs:
  - cos(a, b) = (a · b) / (|a||b|)
- Threshold: ≥ 0.95 → considered duplicates.
- Merge duplicates by:
  - Keeping first occurrence (deterministic by page order).
  - Merging `page_refs`.

---

## 7. Storage Layout (S3)

```
/jobs/{job_id}/raw.pdf
/jobs/{job_id}/pages.json
/jobs/{job_id}/chunks/{chunk_id}.json
/jobs/{job_id}/raw_llm_outputs/{chunk_id}.txt
/jobs/{job_id}/llm_outputs/{chunk_id}.json
/jobs/{job_id}/merged_requirements.json
/jobs/{job_id}/checklist.json
/jobs/{job_id}/status.json
```

---

## 8. Error Handling

- Dramatiq actors have `max_retries` with exponential backoff + jitter.
- Distinguish between:
  - Empty result (valid).
  - Invalid JSON (repair).
- If all retries fail → mark job `failed` with reason in `/status.json`.
- Idempotent: reprocessing same `job_id` overwrites artifacts.

---

## 9. Test Plan (Worker Scope)

- `test_chunk.py`: validate sliding windows and overlap.
- `test_schema.py`: enforce strict schema validation.
- `test_dedup.py`: verify dedup threshold and page_refs merging.
- Smoke test: run on small PDF (mix of text and OCR).
- Mock LLM responses for deterministic tests.

---

## 10. Performance Notes

- Run chunk extraction concurrently across workers.
- Use Gemini Flash for most chunks; Pro only for fallback.
- Chunk size: 5 pages + overlap → avoids token overflow.
- Expected latency: a few minutes per document.

---

## 11. Security

- Do not log or persist secrets.
- Hash `job_id` for directory paths if needed.
- Support on-prem by pointing to MinIO and restricting external calls except Google APIs.

---
