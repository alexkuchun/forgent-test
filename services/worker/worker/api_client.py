from __future__ import annotations
import json
from typing import Any, Dict, List
import httpx
from .config import get_settings


class ApiClient:
    def __init__(self):
        s = get_settings()
        self.base = s.api_base.rstrip("/") if s.api_base else None
        self.token = s.ingest_token
        self.client = httpx.Client(timeout=30.0) if self.base and self.token else None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def mark_processing(self, checklist_id: str):
        if not self.client or not self.base or not self.token:
            return
        url = f"{self.base}/api/internal/checklists/{checklist_id}/status"
        payload = {"status": "PROCESSING"}
        resp = self.client.post(url, headers=self._headers(), content=json.dumps(payload))
        resp.raise_for_status()

    def mark_failed(self, checklist_id: str, error: str):
        if not self.client or not self.base or not self.token:
            return
        url = f"{self.base}/api/internal/checklists/{checklist_id}/status"
        payload = {"status": "FAILED", "error": error}
        resp = self.client.post(url, headers=self._headers(), content=json.dumps(payload))
        resp.raise_for_status()

    def ingest_checklist(self, checklist_id: str, checklist: Dict[str, Any], meta: Dict[str, Any]):
        if not self.client or not self.base or not self.token:
            return
        url = f"{self.base}/api/internal/checklists/{checklist_id}/ingest"
        payload = {
            "items": checklist.get("items", []),
            "meta": meta,
            "prompts": checklist.get("prompts", []),
        }
        resp = self.client.post(url, headers=self._headers(), content=json.dumps(payload))
        resp.raise_for_status()

    def fetch_prompts(self, checklist_id: str) -> List[Dict[str, Any]]:
        if not self.client or not self.base or not self.token:
            return []
        url = f"{self.base}/api/checklists/{checklist_id}/prompts"
        resp = self.client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def close(self):
        if self.client:
            self.client.close()
