"""Thin HTTP seam for the Alex Context API.

The live v3 architecture makes Context API the per-tenant system of record.
This client is intentionally small: Harbor owns orchestration; the API owns
brand context, queue, batches, learnings and workspace isolation.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any


class ContextAPIError(RuntimeError):
    pass


class ContextClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except Exception as e:
            raise ContextAPIError(str(e)) from e

    def get_brand_context(self) -> Any:
        return self._request("GET", "/brand-context")

    def list_queue(self) -> Any:
        return self._request("GET", "/queue")

    def create_batch(self, batch: dict[str, Any]) -> Any:
        return self._request("POST", "/batches", batch)
