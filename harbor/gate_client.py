"""Thin HTTP seam for the persistent Alex Gate API."""
from __future__ import annotations

import json
import urllib.request
from typing import Any


class GateAPIError(RuntimeError):
    pass


class GateClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def review(self, *, draft: str, brief: str, voice_guide: str = "", mode: str = "content") -> Any:
        req = urllib.request.Request(
            self.base_url + "/api/gate",
            data=json.dumps({
                "draft": draft,
                "brief": brief,
                "voice_guide": voice_guide,
                "mode": mode,
            }).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            raise GateAPIError(str(e)) from e
