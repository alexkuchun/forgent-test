from __future__ import annotations

import json
from io import BytesIO
from typing import Any, Dict, List

from anthropic import Anthropic

from .config import get_settings
from .models import Prompt, PromptResult


def _client() -> Anthropic:
    s = get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=s.anthropic_api_key)


def get_client() -> Anthropic:
    return _client()


def upload_document(filename: str, data: bytes, client: Anthropic | None = None) -> str:
    client = client or get_client()
    buffer = BytesIO(data)
    buffer.seek(0)
    result = client.files.create(file=(filename, buffer), purpose="message")
    return result.id


def extract_requirements(chunk_text: str, page_start: int, page_end: int, client: Anthropic | None = None) -> str:
    s = get_settings()
    client = client or get_client()
    system_prompt = (
        "You extract explicit procurement requirements from tender documents.\n"
        "Return STRICT JSON compliant with the provided schema.\n"
        "Do not invent information. If no requirements are present, return {\"requirements\": []}.\n"
        "Do not include any additional text outside JSON."
    )
    user_prompt = (
        f"Document pages: {page_start}-{page_end}\n"
        "Schema: {\n  \"requirements\": [\n    {\n      \"id\": \"string\",\n      \"page_refs\": [0],\n      \"text\": \"string\",\n      \"category\": \"submission|eligibility|technical|financial|other\",\n      \"is_mandatory\": true,\n      \"deadline\": \"YYYY-MM-DD|null\",\n      \"submission_format\": \"string|null\",\n      \"source_quote\": \"string\"\n    }\n  ]\n}\n\n"
        "Extract only explicit requirements with page references from this chunk:\n---\n"
        f"{chunk_text}\n---"
    )
    response = client.messages.create(
        model=s.anthropic_model,
        max_output_tokens=2000,
        temperature=0,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt,
                    }
                ],
            }
        ],
    )
    content = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return content or "{}"


def repair_json(raw_text: str, client: Anthropic | None = None) -> str:
    s = get_settings()
    client = client or get_client()
    response = client.messages.create(
        model=s.anthropic_repair_model,
        max_output_tokens=1000,
        temperature=0,
        system="You repair invalid JSON. Output ONLY valid JSON and nothing else.",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": raw_text,
                    }
                ],
            }
        ],
    )
    content = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return content or raw_text


def evaluate_prompt(
    prompt: Prompt,
    attachments: List[Dict[str, Any]],
    client: Anthropic | None = None,
) -> PromptResult:
    s = get_settings()
    client = client or get_client()

    schema_hint = (
        "{"
        "\n  \"answer\": "
        "string|null,\n  \"boolean_result\": true|false|null,\n"
        "  \"confidence\": number|null,\n  \"evidence\": string|null,\n"
        "  \"page_refs\": [int...],\n  \"error\": string|null,\n"
        "  \"status\": string|null\n}"
    )

    if prompt.prompt_type == "QUESTION":
        system_prompt = (
            "You answer tender-related questions using ONLY the attached documents.\n"
            "Return strict JSON with fields: answer, boolean_result, confidence, evidence, page_refs, status, error."
        )
        task_instruction = (
            "Question: " + prompt.prompt_text.strip() + "\n"
            "If the answer cannot be found, set answer to null and include a brief explanation in evidence."
        )
    else:
        system_prompt = (
            "You evaluate compliance conditions based on the attached documents.\n"
            "Return strict JSON with fields: answer, boolean_result, confidence, evidence, page_refs, status, error."
        )
        task_instruction = (
            "Condition: " + prompt.prompt_text.strip() + "\n"
            "Set boolean_result to true if the documents confirm the condition, false if they contradict it, null if unknown."
        )

    content_entries: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": task_instruction,
        }
    ]
    for att in attachments:
        file_id = att.get("file_id")
        if not file_id:
            continue
        content_entries.append(
            {
                "type": "file",
                "source": {
                    "type": "file_id",
                    "file_id": file_id,
                },
            }
        )

    response = client.messages.create(
        model=s.anthropic_model,
        max_output_tokens=1200,
        temperature=0,
        system=f"{system_prompt}\nRespond ONLY with JSON matching: {schema_hint}",
        messages=[
            {
                "role": "user",
                "content": content_entries,
            }
        ],
    )
    content = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    if not content:
        raise ValueError("Anthropic response did not contain text content")

    data = _parse_json_with_repair(content, client)
    payload = _normalize_prompt_payload(prompt, data)
    return PromptResult.model_validate(payload)


def _parse_json_with_repair(text: str, client: Anthropic) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = repair_json(text, client=client)
        return json.loads(repaired)


def _normalize_prompt_payload(prompt: Prompt, data: Dict[str, Any]) -> Dict[str, Any]:
    answer = data.get("answer") or data.get("answer_text")
    boolean_value = data.get("boolean_result")
    if isinstance(boolean_value, str):
        lowered = boolean_value.strip().lower()
        if lowered in {"true", "yes", "ja"}:
            boolean_value = True
        elif lowered in {"false", "no", "nein"}:
            boolean_value = False
        else:
            boolean_value = None
    elif isinstance(boolean_value, (int, float)):
        boolean_value = bool(boolean_value)
    elif not isinstance(boolean_value, bool):
        boolean_value = None

    confidence = data.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None

    page_refs_raw = data.get("page_refs") or []
    page_refs: List[int] = []
    if isinstance(page_refs_raw, list):
        for value in page_refs_raw:
            try:
                page_refs.append(int(value))
            except (TypeError, ValueError):
                continue

    status = data.get("status") or ("FAILED" if data.get("error") else "READY")

    return {
        "prompt_id": prompt.id,
        "prompt_type": prompt.prompt_type,
        "answer_text": answer,
        "boolean_result": boolean_value,
        "confidence": confidence,
        "evidence": data.get("evidence"),
        "page_refs": page_refs,
        "error": data.get("error"),
        "status": status,
    }
