"""Fly Sprites infrastructure adapter for Harbor.

All Sprites API and SDK details stay in this module. Workers depend only on the
Harbor run contract and never import Fly-specific code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class SpriteError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpriteInfo:
    name: str
    url: str | None = None
    status: str | None = None


class SpritesClient:
    def __init__(
        self,
        token: str | None = None,
        api_base: str | None = None,
        *,
        sdk_client: Any | None = None,
    ):
        self.token = (
            token or os.environ.get("SPRITE_TOKEN") or os.environ.get("SPRITES_TOKEN")
        )
        if not self.token:
            raise SpriteError("SPRITE_TOKEN is required on the Harbor control plane")
        self.api_base = (
            api_base or os.environ.get("SPRITES_API_URL") or "https://api.sprites.dev"
        ).rstrip("/")
        if sdk_client is not None:
            self._client = sdk_client
            return
        try:
            from sprites import SpritesClient as OfficialSpritesClient
        except ImportError as e:
            raise SpriteError(
                "Install production dependency 'sprites-py' to use Sprites"
            ) from e
        self._client = OfficialSpritesClient(
            token=self.token,
            base_url=self.api_base,
        )

    @staticmethod
    def _info(sprite: Any) -> SpriteInfo:
        return SpriteInfo(
            name=sprite.name,
            url=getattr(sprite, "url", None),
            status=getattr(sprite, "status", None),
        )

    @staticmethod
    def _record(sprite: Any) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "id": getattr(sprite, "id", None),
                "name": sprite.name,
                "url": getattr(sprite, "url", None),
                "status": getattr(sprite, "status", None),
                "organization": getattr(sprite, "organization_name", None),
                "labels": list(getattr(sprite, "labels", []) or []),
            }.items()
            if value is not None
        }

    def list_sprites(self) -> list[dict[str, Any]]:
        try:
            from sprites import ListOptions

            records: list[dict[str, Any]] = []
            continuation_token = None
            while True:
                options = (
                    ListOptions(continuation_token=continuation_token)
                    if continuation_token
                    else None
                )
                page = self._client.list_sprites(options)
                records.extend(self._record(sprite) for sprite in page.sprites)
                continuation_token = page.next_continuation_token
                if not page.has_more or not continuation_token:
                    return records
        except Exception as e:
            raise SpriteError(f"Sprites list failed: {e}") from e

    def get_sprite(self, name: str) -> dict[str, Any] | None:
        try:
            from sprites import NotFoundError
        except ImportError as e:
            raise SpriteError(
                "Install production dependency 'sprites-py' to use Sprites"
            ) from e
        try:
            return self._record(self._client.get_sprite(name))
        except NotFoundError:
            return None
        except Exception as e:
            raise SpriteError(f"Sprites get failed for {name}: {e}") from e

    def create_sprite(self, name: str) -> SpriteInfo:
        try:
            from sprites import SpriteError as SDKSpriteError
            from sprites import URLSettings
        except ImportError as e:
            raise SpriteError(
                "Install production dependency 'sprites-py' to use Sprites"
            ) from e
        try:
            sprite = self._client.create_sprite(
                name,
                url_settings=URLSettings(
                    auth="sprite",
                    private_access="admins",
                ),
            )
            return self._info(sprite)
        except SDKSpriteError as create_error:
            # Creation is idempotent only if the same-name Sprite now exists.
            try:
                existing = self.get_sprite(name)
            except SpriteError:
                raise SpriteError(
                    f"Sprites create failed for {name}: {create_error}"
                ) from create_error
            if existing:
                return SpriteInfo(
                    name=existing["name"],
                    url=existing.get("url"),
                    status=existing.get("status"),
                )
            raise SpriteError(
                f"Sprites create failed for {name}: {create_error}"
            ) from create_error
        except Exception as e:
            raise SpriteError(f"Sprites create failed for {name}: {e}") from e

    def write_file(
        self,
        sprite: str,
        path: str,
        data: bytes,
        *,
        mode: str = "0644",
    ) -> None:
        try:
            file_path = self._client.sprite(sprite).filesystem("/") / path.lstrip("/")
            file_path.write_bytes(
                data,
                mode=int(mode, 8),
                mkdir_parents=True,
            )
        except Exception as e:
            raise SpriteError(
                f"Sprite file write failed for {sprite}:{path}: {e}"
            ) from e

    def read_file(self, sprite: str, path: str) -> bytes:
        try:
            file_path = self._client.sprite(sprite).filesystem("/") / path.lstrip("/")
            return file_path.read_bytes()
        except Exception as e:
            raise SpriteError(
                f"Sprite file read failed for {sprite}:{path}: {e}"
            ) from e

    def checkpoint(self, sprite: str, comment: str) -> dict[str, str]:
        try:
            stream = self._client.sprite(sprite).create_checkpoint(comment)
            complete_message = None
            for message in stream:
                if message.type == "error":
                    raise SpriteError(
                        f"Sprite checkpoint failed for {sprite}: "
                        f"{message.error or message.data or 'unknown error'}"
                    )
                if message.type == "complete":
                    complete_message = str(message.data or "complete")
            if complete_message is None:
                raise SpriteError(
                    f"Sprite checkpoint failed for {sprite}: "
                    "stream ended without a complete event"
                )
            return {"status": "complete", "message": complete_message}
        except SpriteError:
            raise
        except Exception as e:
            raise SpriteError(f"Sprite checkpoint failed for {sprite}: {e}") from e

    def exec(self, sprite: str, *command: str) -> bytes:
        try:
            return self._client.sprite(sprite).command(*command).output()
        except Exception as e:
            raise SpriteError(f"Sprite exec failed for {sprite}: {e}") from e
