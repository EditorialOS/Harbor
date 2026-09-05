"""Fly.io Sprites integration for Harbor.

Harbor's control plane runs on a Fly Machine. Customer worker execution runs in
one persistent Sprite per tenant. This module uses the public Sprites REST API
for lifecycle/filesystem calls and the official Python SDK for command exec.

No tenant credentials are stored here. Provider credentials belong in Fly
Sprites Connectors; Harbor stores only non-secret connector metadata such as a
gateway base URL and connection id.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class SpriteError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpriteInfo:
    name: str
    url: str | None = None
    status: str | None = None


class SpritesClient:
    def __init__(self, token: str | None = None, api_base: str | None = None):
        self.token = token or os.environ.get("SPRITE_TOKEN") or os.environ.get("SPRITES_TOKEN")
        if not self.token:
            raise SpriteError("SPRITE_TOKEN is required on the Harbor control plane")
        self.api_base = (api_base or os.environ.get("SPRITES_API_URL") or "https://api.sprites.dev").rstrip("/")

    def _request(self, method: str, path: str, *, body: bytes | None = None,
                 content_type: str | None = "application/json") -> Any:
        headers = {"Authorization": f"Bearer {self.token}"}
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.api_base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                if not raw:
                    return None
                ctype = resp.headers.get("content-type", "")
                if "json" in ctype:
                    return json.loads(raw)
                try:
                    return json.loads(raw)
                except Exception:
                    return raw
        except urllib.error.HTTPError as e:
            detail = e.read()[:1000]
            raise SpriteError(f"Sprites API {method} {path} failed: {e.code} {detail!r}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise SpriteError(f"Sprites API unavailable: {e}") from e

    def list_sprites(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/v1/sprites")
        if isinstance(data, dict):
            return data.get("sprites", []) or data.get("data", []) or []
        return data or []

    def get_sprite(self, name: str) -> dict[str, Any] | None:
        try:
            return self._request("GET", f"/v1/sprites/{urllib.parse.quote(name)}")
        except SpriteError as e:
            if " 404 " in str(e):
                return None
            raise

    def create_sprite(self, name: str) -> SpriteInfo:
        body = json.dumps({"name": name, "url_settings": {"auth": "sprite"}}).encode()
        try:
            data = self._request("POST", "/v1/sprites", body=body)
        except SpriteError as e:
            # Treat already-exists as idempotent by resolving the existing Sprite.
            existing = self.get_sprite(name)
            if existing:
                return SpriteInfo(name=name, url=existing.get("url"), status=existing.get("status"))
            raise e
        return SpriteInfo(name=data.get("name", name), url=data.get("url"), status=data.get("status"))

    def write_file(self, sprite: str, path: str, data: bytes, *, mode: str = "0644") -> None:
        query = urllib.parse.urlencode({"path": path, "mkdir": "true", "mode": mode})
        self._request(
            "PUT",
            f"/v1/sprites/{urllib.parse.quote(sprite)}/fs/write?{query}",
            body=data,
            content_type="application/octet-stream",
        )

    def checkpoint(self, sprite: str, comment: str) -> Any:
        body = json.dumps({"comment": comment}).encode()
        return self._request("POST", f"/v1/sprites/{urllib.parse.quote(sprite)}/checkpoint", body=body)

    def exec(self, sprite: str, *command: str) -> bytes:
        """Execute a command via Fly's official sprites-py SDK.

        The SDK owns the WebSocket/session protocol, which is preferable to
        hand-rolling the exec protocol in Harbor.
        """
        try:
            from sprites import SpritesClient as OfficialSpritesClient  # type: ignore
        except ImportError as e:
            raise SpriteError("Install production dependency 'sprites-py' to execute commands") from e
        client = OfficialSpritesClient(self.token)
        handle = client.sprite(sprite)
        try:
            return handle.command(*command).output()
        except Exception as e:
            raise SpriteError(f"Sprite exec failed for {sprite}: {e}") from e
