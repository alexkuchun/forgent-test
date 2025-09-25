from __future__ import annotations
import json
import logging
import time
from typing import Dict, Any, List
import dramatiq
from pydantic import ValidationError

from .broker import _broker  # noqa: F401 ensures broker is configured
from .config import get_settings
from .s3io import get_object_bytes, put_object_bytes
from .ocr import extract_pages_text
from .chunking import chunk_pages
from .llm import (
    extract_requirements,
    repair_json,
    upload_document,
    evaluate_prompt,
    get_client,
)
from .models import ExtractResponse, Requirement, Prompt, PromptResult
from .dedupe import dedupe_requirements
from .synthesis import synthesize_checklist
from .utils import to_json_bytes
from .api_client import ApiClient

logger = logging.getLogger(__name__)


def _process_chunk(payload: Dict[str, Any], client=None) -> ExtractResponse:
    client = client or get_client()
    job_id = payload["job_id"]
    chunk = payload["chunk"]
    chunk_id = chunk["chunk_id"]

    raw = extract_requirements(
        chunk["text"], chunk["page_start"], chunk["page_end"], client=client
    )
    put_object_bytes(
        f"jobs/{job_id}/raw_llm_outputs/{chunk_id}.txt",
        raw.encode("utf-8"),
        content_type="text/plain",
    )

    try:
        response = ExtractResponse.model_validate_json(raw)
        put_object_bytes(
            f"jobs/{job_id}/llm_outputs/{chunk_id}.json",
            to_json_bytes(response.model_dump()),
            content_type="application/json",
        )
        return response
    except ValidationError as exc:
        logger.warning("Chunk %s produced invalid JSON. Attempting repair.", chunk_id)
        repaired_raw = repair_json(raw, client=client)
        put_object_bytes(
            f"jobs/{job_id}/raw_llm_outputs/{chunk_id}_repaired.txt",
            repaired_raw.encode("utf-8"),
            content_type="text/plain",
        )
        try:
            response = ExtractResponse.model_validate_json(repaired_raw)
            put_object_bytes(
                f"jobs/{job_id}/llm_outputs/{chunk_id}.json",
                to_json_bytes(response.model_dump()),
                content_type="application/json",
            )
            return response
        except ValidationError:
            logger.error("Failed to repair JSON for chunk %s: %s", chunk_id, exc)
            empty = ExtractResponse(requirements=[])
            put_object_bytes(
                f"jobs/{job_id}/llm_outputs/{chunk_id}.json",
                to_json_bytes(empty.model_dump()),
                content_type="application/json",
            )
            return empty


@dramatiq.actor(max_retries=3)
def extract_chunk(payload: Dict[str, Any]):
    _process_chunk(payload)


@dramatiq.actor(max_retries=3, time_limit=60 * 60)
def process_tender(message: Dict[str, Any]):
    """Process a tender job end-to-end."""
    settings = get_settings()
    job_id = message.get("job_id") or message.get("checklist_id")
    checklist_id = message.get("checklist_id") or job_id
    documents: List[Dict[str, Any]] = message.get("documents", [])
    options: Dict[str, Any] = message.get("options", {})

    if not job_id:
        raise ValueError("job_id is required in message")

    start_time = time.time()
    api_client = ApiClient()
    anthropic_client = get_client()
    try:
        api_client.mark_processing(checklist_id)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to notify API about processing state: %s", exc)

    try:
        if not documents:
            raise RuntimeError("No documents supplied to worker")

        all_pages: List[Dict[str, Any]] = []
        page_offset = 0
        attachments: List[Dict[str, Any]] = []
        anthropic_files_meta: List[Dict[str, Any]] = []
        for idx, doc in enumerate(documents, start=1):
            storage_key = doc.get("storage_key")
            if not storage_key:
                logger.warning("Document %s missing storage_key, skipping", doc)
                continue
            pdf_bytes = get_object_bytes(storage_key)
            out_key = f"jobs/{job_id}/documents/{idx:03d}_{doc.get('filename', 'document')}.pdf"
            put_object_bytes(out_key, pdf_bytes, content_type="application/pdf")

            filename = doc.get("filename") or f"document_{idx}.pdf"
            try:
                file_id = upload_document(filename, pdf_bytes, client=anthropic_client)
                attachments.append({"file_id": file_id, "filename": filename})
                anthropic_files_meta.append({"filename": filename, "file_id": file_id})
            except Exception as upload_exc:
                logger.exception("Failed to upload document %s to Anthropic", filename)
                raise RuntimeError(f"Anthropic file upload failed: {filename}") from upload_exc

            pages = extract_pages_text(pdf_bytes)
            for p in pages:
                p["page_no"] = p.get("page_no", 0) + page_offset
            page_offset += len(pages)
            all_pages.extend(pages)

        put_object_bytes(
            f"jobs/{job_id}/pages.json",
            to_json_bytes(all_pages),
            content_type="application/json",
        )

        window = int(options.get("chunk_window_pages", settings.chunk_window_pages))
        overlap = int(options.get("chunk_overlap_pages", settings.chunk_overlap_pages))

        chunks = chunk_pages(all_pages, window, overlap)
        requirements: List[Requirement] = []
        for chunk in chunks:
            put_object_bytes(
                f"jobs/{job_id}/chunks/{chunk['chunk_id']}.json",
                to_json_bytes(chunk),
                content_type="application/json",
            )
            response = _process_chunk({"job_id": job_id, "chunk": chunk}, client=anthropic_client)
            for req in response.requirements:
                requirements.append(req)

        deduped = dedupe_requirements(requirements)
        put_object_bytes(
            f"jobs/{job_id}/merged_requirements.json",
            to_json_bytes({"requirements": [r.model_dump() for r in deduped]}),
            content_type="application/json",
        )

        checklist = synthesize_checklist(deduped)
        checklist_payload = checklist.model_dump()
        put_object_bytes(
            f"jobs/{job_id}/checklist.json",
            to_json_bytes(checklist_payload),
            content_type="application/json",
        )

        prompt_results: List[PromptResult] = []
        prompt_results_payload: List[Dict[str, Any]] = []
        prompts_raw: List[Dict[str, Any]] = []
        try:
            prompts_raw = api_client.fetch_prompts(checklist_id)
        except Exception as exc:
            logger.warning("Failed to fetch prompts for checklist %s: %s", checklist_id, exc)

        prompts: List[Prompt] = []
        for item in prompts_raw:
            try:
                prompt_type = str(item.get("prompt_type", "QUESTION")).upper()
                if prompt_type not in {"QUESTION", "CONDITION"}:
                    prompt_type = "QUESTION"
                prompts.append(
                    Prompt(
                        id=int(item["id"]),
                        prompt_text=str(item.get("prompt_text", "")),
                        prompt_type=prompt_type,  # type: ignore[arg-type]
                    )
                )
            except Exception as exc:
                logger.warning("Skipping prompt due to parse error: %s", exc)

        for prompt in prompts:
            try:
                result = evaluate_prompt(
                    prompt,
                    attachments=[{"file_id": a["file_id"]} for a in attachments],
                    client=anthropic_client,
                )
            except Exception as exc:
                logger.exception(
                    "Prompt evaluation failed for prompt %s on checklist %s",
                    prompt.id,
                    checklist_id,
                )
                result = PromptResult(
                    prompt_id=prompt.id,
                    prompt_type=prompt.prompt_type,
                    answer_text=None,
                    boolean_result=None,
                    confidence=None,
                    evidence=None,
                    page_refs=[],
                    status="FAILED",
                    error=str(exc),
                )
            prompt_results.append(result)

        if prompt_results:
            prompt_results_payload = [res.model_dump() for res in prompt_results]
            checklist_payload["prompts"] = prompt_results_payload

        meta = {
            "items": len(checklist.items),
            "duration_seconds": round(time.time() - start_time, 2),
        }
        if anthropic_files_meta:
            meta["anthropicFiles"] = anthropic_files_meta
        if prompt_results:
            meta["promptsEvaluated"] = len(prompt_results)
        put_object_bytes(
            f"jobs/{job_id}/status.json",
            to_json_bytes({"status": "done", "items": len(checklist.items)}),
            content_type="application/json",
        )

        try:
            api_client.ingest_checklist(checklist_id, checklist_payload, meta)
        except Exception as exc:  # pragma: no cover - best effort
            logger.exception("Failed to ingest checklist %s: %s", checklist_id, exc)
            raise
    except Exception as exc:
        logger.exception("Worker failed for checklist %s: %s", checklist_id, exc)
        try:
            api_client.mark_failed(checklist_id, str(exc))
        except Exception as notify_exc:  # pragma: no cover - best effort
            logger.error("Failed to notify API about failure: %s", notify_exc)
        put_object_bytes(
            f"jobs/{job_id}/status.json",
            to_json_bytes({"status": "failed", "error": str(exc)}),
            content_type="application/json",
        )
        raise
    finally:
        api_client.close()
