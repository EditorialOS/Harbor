"""Provision and dispatch Harbor worker runs into tenant Sprites."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .sprites_client import SpriteError, SpritesClient


class SpriteRunner:
    def __init__(self, client: SpritesClient | None = None):
        self.client = client or SpritesClient()
        configured_wheel = os.environ.get("HARBOR_RUNTIME_WHEEL")
        wheel_dir = Path(
            os.environ.get("HARBOR_RUNTIME_WHEEL_DIR", "/opt/harbor/wheels")
        )
        if configured_wheel:
            self.wheel_path = Path(configured_wheel)
        else:
            wheels = sorted(wheel_dir.glob("*.whl"))
            self.wheel_path = (
                wheels[0] if len(wheels) == 1 else wheel_dir / "runtime-wheel-not-found"
            )

    def provision(self, sprite_name: str) -> dict[str, Any]:
        info = self.client.create_sprite(sprite_name)
        if not self.wheel_path.exists():
            raise SpriteError(
                f"runtime wheel not found at {self.wheel_path}; production image must include HARBOR_RUNTIME_WHEEL"
            )
        remote_wheel = f"/tmp/{self.wheel_path.name}"
        self.client.write_file(sprite_name, remote_wheel, self.wheel_path.read_bytes())
        self.client.exec(
            sprite_name, "python3", "-m", "pip", "install", "--upgrade", remote_wheel
        )
        self.client.exec(
            sprite_name,
            "mkdir",
            "-p",
            "/workspace/Work/reports",
            "/workspace/Work/runs",
        )
        self.client.checkpoint(sprite_name, "Harbor runtime installed")
        return {"sprite_name": info.name, "url": info.url, "status": info.status}

    def run(self, sprite_name: str, run_spec: dict[str, Any]) -> dict[str, Any]:
        spec_path = "/tmp/harbor-run.json"
        self.client.write_file(sprite_name, spec_path, json.dumps(run_spec).encode())
        output = self.client.exec(
            sprite_name,
            "python3",
            "-m",
            "harbor.sprite_entrypoint",
            "--spec",
            spec_path,
        )
        try:
            return json.loads(output.decode())
        except Exception as e:
            raise SpriteError(
                f"worker returned non-JSON output: {output[:1000]!r}"
            ) from e
