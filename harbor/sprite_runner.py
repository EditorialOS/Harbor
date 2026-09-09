"""Provision and dispatch Harbor worker runs into tenant Sprites."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

from .sprites_client import SpriteError, SpritesClient

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SPRITE_PYTHON = "/.sprite/bin/python3"
_RUNTIME_MARKER = "/workspace/.harbor/runtime.sha256"
_REPORT_PATH_PATTERN = re.compile(
    r"^/workspace/Work/reports/[A-Za-z0-9][A-Za-z0-9._-]{0,255}\.md$"
)


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
        self.runtime_fingerprint = (
            hashlib.sha256(self.wheel_path.read_bytes()).hexdigest()
            if self.wheel_path.exists()
            else ""
        )

    def ensure_runtime(self, sprite_name: str, *, force: bool = False) -> bool:
        """Install the released runtime when a tenant Sprite is missing it."""
        if not self.wheel_path.exists() or not self.runtime_fingerprint:
            raise SpriteError(
                f"runtime wheel not found at {self.wheel_path}; production image must contain exactly one wheel in HARBOR_RUNTIME_WHEEL_DIR"
            )
        if not force:
            try:
                installed = self.client.read_file(sprite_name, _RUNTIME_MARKER)
                if installed.decode("ascii").strip() == self.runtime_fingerprint:
                    return False
            except (SpriteError, UnicodeDecodeError):
                pass
        remote_wheel = f"/tmp/{self.wheel_path.name}"
        self.client.write_file(sprite_name, remote_wheel, self.wheel_path.read_bytes())
        self.client.exec(
            sprite_name,
            _SPRITE_PYTHON,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--force-reinstall",
            remote_wheel,
        )
        self.client.exec(
            sprite_name,
            "mkdir",
            "-p",
            "/workspace/Work/reports",
            "/workspace/Work/runs",
            "/workspace/.harbor",
        )
        self.client.checkpoint(sprite_name, "Harbor runtime installed")
        self.client.write_file(
            sprite_name,
            _RUNTIME_MARKER,
            (self.runtime_fingerprint + "\n").encode("ascii"),
            mode="0600",
        )
        return True

    def provision(self, sprite_name: str) -> dict[str, Any]:
        if not self.wheel_path.exists():
            raise SpriteError(
                f"runtime wheel not found at {self.wheel_path}; production image must contain exactly one wheel in HARBOR_RUNTIME_WHEEL_DIR"
            )
        info = self.client.create_sprite(sprite_name)
        self.ensure_runtime(sprite_name, force=True)
        return {
            "sprite_name": info.name,
            "url": info.url,
            "status": info.status,
            "runtime_updated": True,
        }

    def run(self, sprite_name: str, run_spec: dict[str, Any]) -> dict[str, Any]:
        run_id = run_spec.get("run_id")
        if not isinstance(run_id, str) or not _RUN_ID_PATTERN.fullmatch(run_id):
            raise SpriteError("run spec contains a missing or invalid run_id")
        self.ensure_runtime(sprite_name)
        spec_path = f"/tmp/harbor-runs/{run_id}.json"
        self.client.write_file(
            sprite_name,
            spec_path,
            json.dumps(run_spec).encode(),
            mode="0600",
        )
        output = self.client.exec(
            sprite_name,
            _SPRITE_PYTHON,
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

    def verify_connection(
        self, sprite_name: str, connection_spec: dict[str, Any]
    ) -> dict[str, Any]:
        self.ensure_runtime(sprite_name)
        probe_id = secrets.token_hex(12)
        spec_path = f"/tmp/harbor-connections/{probe_id}.json"
        self.client.write_file(
            sprite_name,
            spec_path,
            json.dumps(connection_spec).encode(),
            mode="0600",
        )
        output = self.client.exec(
            sprite_name,
            _SPRITE_PYTHON,
            "-m",
            "harbor.connection_probe",
            "--spec",
            spec_path,
        )
        try:
            return json.loads(output.decode())
        except Exception as e:
            raise SpriteError(
                f"connection probe returned non-JSON output: {output[:1000]!r}"
            ) from e

    def create_beehiiv_connector(
        self, sprite_name: str, api_key: str
    ) -> dict[str, Any]:
        """Pass a Beehiiv credential directly to Fly's encrypted connector store."""
        return self.client.create_custom_api_connector(
            api_key=api_key,
            sprite_name=sprite_name,
            connection_name=f"Harbor beehiiv · {sprite_name}",
            base_api_url="https://api.beehiiv.com/v2",
            test_url="https://api.beehiiv.com/v2/publications",
            auth_header_prefix="Bearer",
            allowed_endpoints=("/publications", "/publications/*"),
        )

    def read_report(self, sprite_name: str, report_path: str) -> str:
        """Read only a worker-produced report from the fixed tenant workspace."""
        if not _REPORT_PATH_PATTERN.fullmatch(report_path):
            raise SpriteError("worker returned an invalid report path")
        data = self.client.read_file(sprite_name, report_path)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise SpriteError("worker report is not valid UTF-8") from e
