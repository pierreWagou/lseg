"""Session factory tests — no network, no credentials."""

import lseg.data as ld
import pytest

from lseg_extractor.config import Settings
from lseg_extractor.session import open_lseg_session, session_scope


class _FakeSession:
    def __init__(self) -> None:
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def registered_default(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stub ld.session.set_default (it type-checks real sessions)."""
    registered: dict = {}
    monkeypatch.setattr(
        ld.session, "set_default", lambda session: registered.setdefault("session", session)
    )
    return registered


def test_effective_session_auto_prefers_platform_when_creds_present() -> None:
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        LSEG_SESSION="auto",
        LSEG_APP_KEY="key",
        LSEG_CLIENT_ID="id",
        LSEG_CLIENT_SECRET="secret",
    )
    assert s.effective_session() == "platform-ldpv2"


def test_effective_session_auto_falls_back_to_desktop() -> None:
    s = Settings(_env_file=None, LSEG_SESSION="auto")  # type: ignore[call-arg]
    assert s.effective_session() == "desktop"


def test_platform_missing_creds_raises_helpful_error() -> None:
    s = Settings(_env_file=None, LSEG_SESSION="platform-ldpv2")  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="LSEG_APP_KEY"):
        open_lseg_session(s)


def test_desktop_uses_app_key_definition(
    monkeypatch: pytest.MonkeyPatch, registered_default: dict
) -> None:
    fake = _FakeSession()
    captured: dict = {}

    class FakeDefinition:
        def __init__(self, app_key: str | None = None, **_: object) -> None:
            captured["app_key"] = app_key

        def get_session(self) -> _FakeSession:
            return fake

    monkeypatch.setattr(ld.session.desktop, "Definition", FakeDefinition)
    s = Settings(_env_file=None, LSEG_SESSION="desktop", LSEG_APP_KEY="my-key")  # type: ignore[call-arg]
    session = open_lseg_session(s)
    assert session is fake and fake.opened
    assert captured["app_key"] == "my-key"
    assert registered_default["session"] is fake


def test_platform_builds_client_credentials(
    monkeypatch: pytest.MonkeyPatch, registered_default: dict
) -> None:
    fake = _FakeSession()
    captured: dict = {}

    class FakeGrant:
        def __init__(self, client_id: str, client_secret: str, token_scope: str) -> None:
            captured.update(
                client_id=client_id, client_secret=client_secret, token_scope=token_scope
            )

    class FakeDefinition:
        def __init__(self, app_key: str | None, grant: object, signon_control: bool) -> None:
            captured.update(app_key=app_key, signon=signon_control, grant=grant)

        def get_session(self) -> _FakeSession:
            return fake

    monkeypatch.setattr(ld.session.platform, "ClientCredentials", FakeGrant)
    monkeypatch.setattr(ld.session.platform, "Definition", FakeDefinition)
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        LSEG_SESSION="platform-ldpv2",
        LSEG_APP_KEY="ak",
        LSEG_CLIENT_ID="cid",
        LSEG_CLIENT_SECRET="csec",
    )
    assert open_lseg_session(s) is fake
    assert registered_default["session"] is fake
    assert captured == {
        "client_id": "cid",
        "client_secret": "csec",
        "token_scope": "trapi",
        "app_key": "ak",
        "signon": True,
        "grant": captured["grant"],
    }


def test_session_scope_always_closes(
    monkeypatch: pytest.MonkeyPatch, registered_default: dict
) -> None:
    fake = _FakeSession()

    class FakeDefinition:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def get_session(self) -> _FakeSession:
            return fake

    monkeypatch.setattr(ld.session.desktop, "Definition", FakeDefinition)
    s = Settings(_env_file=None, LSEG_SESSION="desktop", LSEG_APP_KEY="k")  # type: ignore[call-arg]
    with session_scope(s) as session:
        assert session is fake
        assert registered_default["session"] is fake
    assert fake.closed


def test_open_registers_default_session(
    monkeypatch: pytest.MonkeyPatch, registered_default: dict
) -> None:
    """Regression: Access-layer helpers need the opened session as default."""
    fake = _FakeSession()

    class FakeDefinition:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def get_session(self) -> _FakeSession:
            return fake

    monkeypatch.setattr(ld.session.desktop, "Definition", FakeDefinition)
    s = Settings(_env_file=None, LSEG_SESSION="desktop", LSEG_APP_KEY="k")  # type: ignore[call-arg]
    assert open_lseg_session(s) is fake
    assert registered_default["session"] is fake
