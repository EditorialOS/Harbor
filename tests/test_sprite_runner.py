from pathlib import Path

import pytest

from harbor.sprite_runner import SpriteRunner
from harbor.sprites_client import SpriteError, SpriteInfo


class FakeSpritesClient:
    def __init__(self):
        self.created = []
        self.writes = []
        self.commands = []
        self.files = {}
        self.checkpoints = 0

    def create_sprite(self, name):
        self.created.append(name)
        return SpriteInfo(
            name=name, url="https://sprite.example.test", status="running"
        )

    def write_file(self, sprite, path, data, *, mode="0644"):
        self.writes.append((sprite, path, data, mode))
        self.files[(sprite, path)] = data

    def read_file(self, sprite, path):
        self.read = (sprite, path)
        if path.endswith("runtime.sha256"):
            if (sprite, path) not in self.files:
                raise SpriteError("file not found")
            return self.files[(sprite, path)]
        return b"# Safe report\n"

    def exec(self, sprite, *command):
        self.commands.append((sprite, command))
        if "harbor.sprite_entrypoint" in command:
            return b'{"status":"completed"}'
        if "harbor.connection_probe" in command:
            return b'{"status":"verified","provider":"beehiiv"}'
        return b""

    def checkpoint(self, sprite, comment):
        self.checkpoints += 1
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
    assert "--force-reinstall" in client.commands[0][1]
    assert client.commands[0][1][-1] == f"/tmp/{wheel.name}"
    assert client.writes[-1][1] == "/workspace/.harbor/runtime.sha256"
    assert client.writes[-1][3] == "0600"


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
    runner = SpriteRunner(client)
    client.files[("tenant-sprite", "/workspace/.harbor/runtime.sha256")] = (
        runner.runtime_fingerprint + "\n"
    ).encode()

    result = runner.run(
        "tenant-sprite",
        {"run_id": "run_safe-123", "worker": "newsletter-intelligence"},
    )

    assert result["status"] == "completed"
    assert client.writes[0][1] == "/tmp/harbor-runs/run_safe-123.json"
    assert client.writes[0][3] == "0600"
    assert client.commands[0][1][0] == "/.sprite/bin/python3"


def test_run_upgrades_stale_runtime_once(monkeypatch, tmp_path: Path):
    wheel = tmp_path / "harbor_ai_worker_runtime-1.0.0rc1-py3-none-any.whl"
    wheel.write_bytes(b"release candidate wheel")
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL", str(wheel))
    client = FakeSpritesClient()
    client.files[("tenant-sprite", "/workspace/.harbor/runtime.sha256")] = b"old\n"
    runner = SpriteRunner(client)

    runner.run(
        "tenant-sprite",
        {"run_id": "run_upgrade-1", "worker": "newsletter-intelligence"},
    )
    installs_after_first = sum(
        "--force-reinstall" in command for _, command in client.commands
    )
    runner.run(
        "tenant-sprite",
        {"run_id": "run_upgrade-2", "worker": "newsletter-intelligence"},
    )

    assert installs_after_first == 1
    assert sum("--force-reinstall" in command for _, command in client.commands) == 1
    assert client.checkpoints == 1


def test_run_rejects_path_like_or_missing_run_ids(monkeypatch, tmp_path: Path):
    wheel = tmp_path / "harbor_ai_worker_runtime-0.9.0a0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL", str(wheel))
    runner = SpriteRunner(FakeSpritesClient())

    for run_id in (None, "../escape", "/tmp/escape", "has spaces"):
        with pytest.raises(SpriteError, match="invalid run_id"):
            runner.run("tenant-sprite", {"run_id": run_id})


def test_connection_probe_uses_private_random_internal_spec_path(
    monkeypatch, tmp_path: Path
):
    wheel = tmp_path / "harbor_ai_worker_runtime-0.9.0a0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    monkeypatch.setenv("HARBOR_RUNTIME_WHEEL", str(wheel))
    client = FakeSpritesClient()
    runner = SpriteRunner(client)
    client.files[("tenant-sprite", "/workspace/.harbor/runtime.sha256")] = (
        runner.runtime_fingerprint + "\n"
    ).encode()

    result = runner.verify_connection(
        "tenant-sprite", {"provider": "beehiiv"}
    )

    assert result == {"status": "verified", "provider": "beehiiv"}
    assert client.writes[0][1].startswith("/tmp/harbor-connections/")
    assert client.writes[0][1].endswith(".json")
    assert client.writes[0][3] == "0600"
    assert client.commands[0][1][:3] == (
        "/.sprite/bin/python3",
        "-m",
        "harbor.connection_probe",
    )


def test_read_report_accepts_only_fixed_workspace_report_paths():
    client = FakeSpritesClient()
    runner = SpriteRunner(client)

    assert (
        runner.read_report(
            "tenant-sprite", "/workspace/Work/reports/2026-09-06-report.md"
        )
        == "# Safe report\n"
    )
    assert client.read == (
        "tenant-sprite",
        "/workspace/Work/reports/2026-09-06-report.md",
    )

    for unsafe_path in (
        "/etc/passwd",
        "/workspace/Work/reports/../secrets.md",
        "/workspace/Work/reports/report.txt",
        "workspace/Work/reports/report.md",
    ):
        with pytest.raises(SpriteError, match="invalid report path"):
            runner.read_report("tenant-sprite", unsafe_path)
