from pathlib import Path

import pytest

from harbor.sprite_runner import SpriteRunner
from harbor.sprites_client import SpriteError, SpriteInfo


class FakeSpritesClient:
    def __init__(self):
        self.created = []
        self.writes = []
        self.commands = []

    def create_sprite(self, name):
        self.created.append(name)
        return SpriteInfo(
            name=name, url="https://sprite.example.test", status="running"
        )

    def write_file(self, sprite, path, data, *, mode="0644"):
        self.writes.append((sprite, path, data, mode))

    def exec(self, sprite, *command):
        self.commands.append((sprite, command))
        if "harbor.sprite_entrypoint" in command:
            return b'{"status":"completed"}'
        return b""

    def checkpoint(self, sprite, comment):
        return {"ok": True}


def test_provision_preserves_valid_wheel_filename(tmp_path: Path, monkeypatch):
    wheel = tmp_path / "harbor_ai_worker_runtime-0.9.0a0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL", str(wheel))
    client = FakeSpritesClient()

    result = SpriteRunner(client).provision("tenant-sprite")

    assert result["sprite_name"] == "tenant-sprite"
    assert client.writes[0][1] == f"/tmp/{wheel.name}"
    assert client.commands[0][1][0] == "/.sprite/bin/python3"
    assert client.commands[0][1][-1] == f"/tmp/{wheel.name}"


def test_runner_discovers_the_single_bundled_wheel(tmp_path: Path, monkeypatch):
    wheel = tmp_path / "harbor_ai_worker_runtime-0.9.0a0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    monkeypatch.delenv("HARBOR_RUNTIME_WHEEL", raising=False)
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL_DIR", str(tmp_path))

    assert SpriteRunner(FakeSpritesClient()).wheel_path == wheel


def test_provision_does_not_create_sprite_without_runtime_wheel(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL", str(tmp_path / "missing.whl"))
    client = FakeSpritesClient()

    with pytest.raises(SpriteError, match="runtime wheel not found"):
        SpriteRunner(client).provision("tenant-sprite")

    assert client.created == []


def test_run_uses_private_unique_internal_spec_path(monkeypatch, tmp_path: Path):
    wheel = tmp_path / "harbor_ai_worker_runtime-0.9.0a0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL", str(wheel))
    client = FakeSpritesClient()

    result = SpriteRunner(client).run(
        "tenant-sprite",
        {"run_id": "run_safe-123", "worker": "newsletter-intelligence"},
    )

    assert result["status"] == "completed"
    assert client.writes[0][1] == "/tmp/harbor-runs/run_safe-123.json"
    assert client.writes[0][3] == "0600"
    assert client.commands[0][1][0] == "/.sprite/bin/python3"


def test_run_rejects_path_like_or_missing_run_ids(monkeypatch, tmp_path: Path):
    wheel = tmp_path / "harbor_ai_worker_runtime-0.9.0a0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL", str(wheel))
    runner = SpriteRunner(FakeSpritesClient())

    for run_id in (None, "../escape", "/tmp/escape", "has spaces"):
        with pytest.raises(SpriteError, match="invalid run_id"):
            runner.run("tenant-sprite", {"run_id": run_id})
