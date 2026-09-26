"""Dual-auth session factory: Desktop Workspace vs Platform LDPv2.

- Desktop (`desktop.workspace`): Workspace/Eikon app must be running locally.
  Only an AppKey is required.
- Platform LDPv2 (headless OAuth2 client credentials): `app_key` + `client_id`
  (service ID) + `client_secret`, built explicitly in code so the same path
  works from CLI, REST API, or frontend backends.

When no explicit credentials are configured we fall back to
`ld.open_session()` which reads `lseg-data.config.json` (default session).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import lseg.data as ld

from lseg_extractor.config import Settings, get_settings

_DESKTOP_HINT = (
    "Desktop session failed. Is LSEG Workspace (or Eikon) running on this machine? "
    "It must be open (listens on port 9000+) and your AppKey must be set "
    "(LSEG_APP_KEY or lseg-data.config.json desktop.workspace app-key)."
)
_PLATFORM_HINT = (
    "Platform session failed. Check LSEG_APP_KEY / LSEG_CLIENT_ID / "
    "LSEG_CLIENT_SECRET (LDPv2 OAuth2 client credentials) and network access "
    "to the LSEG Data Platform."
)


def open_lseg_session(settings: Settings | None = None) -> Any:
    """Open and return a live LSEG session.

    Raises:
        RuntimeError: with an actionable hint when auth/connection fails.
    """
    settings = settings or get_settings()
    kind = settings.effective_session()

    try:
        if kind == "platform-ldpv2":
            session = _open_platform_session(settings)
        else:
            session = _open_desktop_session(settings)
        # Access-layer helpers (ld.get_data / ld.get_history) resolve the
        # library default session implicitly. Sessions built via
        # Definition(...).get_session() are NOT registered by default
        # (unlike ld.open_session()), so register explicitly here.
        ld.session.set_default(session)
        return session
    except RuntimeError:
        raise
    except Exception as exc:
        hint = _PLATFORM_HINT if kind == "platform-ldpv2" else _DESKTOP_HINT
        raise RuntimeError(f"{hint} Underlying error: {exc}") from exc


def _open_desktop_session(settings: Settings) -> Any:
    if settings.app_key:
        session = ld.session.desktop.Definition(app_key=settings.app_key).get_session()
    else:
        # Fall back to lseg-data.config.json default session.
        session = ld.open_session()
    session.open()
    return session


def _open_platform_session(settings: Settings) -> Any:
    if not settings.has_platform_credentials:
        raise RuntimeError(
            "Platform LDPv2 session needs LSEG_APP_KEY, LSEG_CLIENT_ID and "
            "LSEG_CLIENT_SECRET. " + _PLATFORM_HINT
        )
    grant = ld.session.platform.ClientCredentials(
        client_id=settings.client_id or "",
        client_secret=settings.client_secret or "",
        token_scope=settings.token_scope,
    )
    session = ld.session.platform.Definition(
        app_key=settings.app_key,
        grant=grant,
        signon_control=True,
    ).get_session()
    session.open()
    return session


def close_session(session: Any) -> None:
    """Best-effort session close (safe to call with None)."""
    if session is None:
        return
    try:
        session.close()
    except Exception:  # noqa: BLE001, S110 — best-effort cleanup
        pass


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Any]:
    """Context manager yielding an open session, always closing it.

    Example:
        with session_scope() as _:
            df = get_snapshot(["IBM.N"], ["BID", "ASK"])
    """

    session = open_lseg_session(settings)
    try:
        yield session
    finally:
        close_session(session)
