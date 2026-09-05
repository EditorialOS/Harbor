from pathlib import Path

from harbor.sprite_runner import SpriteRunner
from harbor.sprites_client import SpriteInfo


class FakeSpritesClient:
    def __init__(self):
        self.writes = []
        self.commands = []

    def create_sprite(self, name):
        return SpriteInfo(
            name=name, url="https://sprite.example.test", status="running"
        )

    def write_file(self, sprite, path, data):
        self.writes.append((sprite, path, data))

    def exec(self, sprite, *command):
        self.commands.append((sprite, command))
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
    assert client.commands[0][1][-1] == f"/tmp/{wheel.name}"


def test_runner_discovers_the_single_bundled_wheel(tmp_path: Path, monkeypatch):
    wheel = tmp_path / "harbor_ai_worker_runtime-0.9.0a0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    monkeypatch.delenv("HARBOR_RUNTIME_WHEEL", raising=False)
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL_DIR", str(tmp_path))

    assert SpriteRunner(FakeSpritesClient()).wheel_path == wheel
