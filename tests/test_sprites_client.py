from dataclasses import dataclass

import pytest
from sprites import NotFoundError
from sprites import SpriteError as SDKSpriteError

from harbor.sprites_client import SpriteError, SpritesClient


@dataclass
class Message:
    type: str
    data: str | None = None
    error: str | None = None


class FakePath:
    def __init__(self, path):
        self.path = path
        self.write = None
        self.contents = b"report contents"

    def write_bytes(self, data, *, mode, mkdir_parents):
        self.write = (data, mode, mkdir_parents)

    def read_bytes(self):
        return self.contents


class FakeFilesystem:
    def __init__(self):
        self.path = None

    def __truediv__(self, path):
        self.path = FakePath(path)
        return self.path


class FakeCommand:
    def __init__(self, output=b"ok\n"):
        self._output = output

    def output(self):
        return self._output


class FakeSprite:
    def __init__(self, name="harbor-test", checkpoint_messages=None):
        self.name = name
        self.id = "sprite-id"
        self.url = "https://sprite.example.test"
        self.status = "running"
        self.organization_name = "example-org"
        self.labels = ["harbor"]
        self.fs = FakeFilesystem()
        self.checkpoint_messages = checkpoint_messages or [
            Message("info", "creating"),
            Message("complete", "Checkpoint v1 created"),
        ]
        self.last_command = None

    def filesystem(self, working_dir):
        assert working_dir == "/"
        return self.fs

    def create_checkpoint(self, comment):
        assert comment
        return iter(self.checkpoint_messages)

    def command(self, *command):
        self.last_command = command
        return FakeCommand()


class FakePage:
    def __init__(self, sprites, *, has_more=False, next_continuation_token=None):
        self.sprites = sprites
        self.has_more = has_more
        self.next_continuation_token = next_continuation_token


class FakeSDK:
    def __init__(self, sprite=None):
        self.value = sprite or FakeSprite()
        self.create_error = None
        self.get_error = None
        self.url_settings = None
        self.list_options = []

    def create_sprite(self, name, *, url_settings):
        self.url_settings = url_settings
        if self.create_error:
            raise self.create_error
        self.value.name = name
        return self.value

    def get_sprite(self, name):
        if self.get_error:
            raise self.get_error
        self.value.name = name
        return self.value

    def list_sprites(self, options=None):
        self.list_options.append(options)
        return FakePage([self.value])

    def sprite(self, name):
        self.value.name = name
        return self.value


def _client(sdk):
    return SpritesClient(token="local-test-token", sdk_client=sdk)


def test_sdk_adapter_creates_private_sprite_and_maps_metadata():
    sdk = FakeSDK()
    client = _client(sdk)

    info = client.create_sprite("harbor-tenant")

    assert info.name == "harbor-tenant"
    assert info.status == "running"
    assert sdk.url_settings.auth == "sprite"
    assert sdk.url_settings.private_access == "admins"
    assert client.list_sprites()[0]["organization"] == "example-org"


def test_list_follows_sdk_pagination():
    sdk = FakeSDK(FakeSprite("first"))
    pages = iter(
        [
            FakePage(
                [FakeSprite("first")],
                has_more=True,
                next_continuation_token="next-page",
            ),
            FakePage([FakeSprite("second")]),
        ]
    )

    def list_sprites(options=None):
        sdk.list_options.append(options)
        return next(pages)

    sdk.list_sprites = list_sprites
    records = _client(sdk).list_sprites()

    assert [record["name"] for record in records] == ["first", "second"]
    assert sdk.list_options[0] is None
    assert sdk.list_options[1].continuation_token == "next-page"


def test_create_is_idempotent_only_when_sprite_exists():
    sdk = FakeSDK()
    sdk.create_error = SDKSpriteError("already exists")
    client = _client(sdk)

    assert client.create_sprite("harbor-existing").name == "harbor-existing"

    sdk.get_error = NotFoundError("missing")
    with pytest.raises(SpriteError, match="Sprites create failed"):
        client.create_sprite("harbor-missing")


def test_get_returns_none_only_for_not_found():
    sdk = FakeSDK()
    sdk.get_error = NotFoundError("missing")
    assert _client(sdk).get_sprite("missing") is None

    sdk.get_error = SDKSpriteError("authorization failure")
    with pytest.raises(SpriteError, match="Sprites get failed"):
        _client(sdk).get_sprite("private")


def test_filesystem_and_exec_use_official_sdk_contract():
    sdk = FakeSDK()
    client = _client(sdk)

    client.write_file("harbor-tenant", "/tmp/run.json", b"{}", mode="0600")
    assert sdk.value.fs.path.path == "tmp/run.json"
    assert sdk.value.fs.path.write == (b"{}", 0o600, True)

    assert client.read_file("harbor-tenant", "/workspace/report.md") == b"report contents"
    assert sdk.value.fs.path.path == "workspace/report.md"

    assert client.exec("harbor-tenant", "echo", "ok") == b"ok\n"
    assert sdk.value.last_command == ("echo", "ok")


def test_checkpoint_requires_terminal_complete_event():
    success = _client(FakeSDK())
    assert success.checkpoint("harbor-tenant", "installed")["status"] == "complete"

    error_sprite = FakeSprite(
        checkpoint_messages=[Message("error", error="snapshot failed")]
    )
    with pytest.raises(SpriteError, match="snapshot failed"):
        _client(FakeSDK(error_sprite)).checkpoint("harbor-tenant", "installed")

    incomplete_sprite = FakeSprite(checkpoint_messages=[Message("info", "creating")])
    with pytest.raises(SpriteError, match="without a complete event"):
        _client(FakeSDK(incomplete_sprite)).checkpoint("harbor-tenant", "installed")
