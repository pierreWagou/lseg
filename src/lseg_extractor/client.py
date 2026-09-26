"""Reusable data primitives — import-safe for CLI, REST API, or frontends.

Each function returns a `pandas.DataFrame` and performs no printing or file
I/O. Call them inside :func:`lseg_extractor.session.session_scope` (or pass
an explicit open `session`) so authentication is handled in one place.

Covers the four main read patterns (scope TBD by user):
- snapshot quotes / reference fields (Access layer `ld.get_data`)
- historical time series (Access layer `ld.get_history`)
- fundamentals & reference (Content layer `fundamental_and_reference`)
- news headlines + instrument search (Content layer)
"""

from typing import Any

import pandas as pd

__all__ = [
    "get_fundamentals",
    "get_history",
    "get_news_headlines",
    "get_snapshot",
    "search_instruments",
]


def _require_non_empty(name: str, values: list[str]) -> list[str]:
    cleaned = [v.strip() for v in values if v and v.strip()]
    if not cleaned:
        raise ValueError(f"'{name}' must contain at least one instrument/field.")
    return cleaned


def get_snapshot(
    universe: list[str],
    fields: list[str],
    parameters: dict | None = None,
    session: Any | None = None,
) -> pd.DataFrame:
    """Pricing snapshot + reference fields, e.g. BID/ASK/TR.Revenue.

    Example:
        with session_scope():
            df = get_snapshot(["IBM.N", "VOD.L"], ["BID", "ASK"])
    """
    import lseg.data as ld

    universe = _require_non_empty("universe", universe)
    fields = _require_non_empty("fields", fields)
    kwargs: dict = {"universe": universe, "fields": fields}
    if parameters is not None:
        kwargs["parameters"] = parameters
    if session is not None:
        # Access-layer helpers use the default session; an explicit session
        # is accepted for future-proofing but currently unused.
        kwargs.pop("session", None)
    df = ld.get_data(**kwargs)
    return _ensure_frame(df, "snapshot")


def get_history(
    universe: list[str],
    interval: str = "1D",
    start: str | None = None,
    end: str | None = None,
    fields: list[str] | None = None,
    adjustments: str | None = None,
    count: int | None = None,
    session: Any | None = None,
) -> pd.DataFrame:
    """Historical candles / time series, e.g. daily closes for a RIC."""
    import lseg.data as ld

    universe = _require_non_empty("universe", universe)
    kwargs: dict = {"universe": universe, "interval": interval}
    if fields:
        kwargs["fields"] = fields
    if start:
        kwargs["start"] = start
    if end:
        kwargs["end"] = end
    if adjustments:
        kwargs["adjustments"] = adjustments
    if count:
        kwargs["count"] = count
    df = ld.get_history(**kwargs)
    return _ensure_frame(df, "history")


def get_fundamentals(
    universe: list[str],
    fields: list[str],
    parameters: dict | None = None,
    session: Any | None = None,
) -> pd.DataFrame:
    """Company fundamentals / reference, e.g. TR.Revenue, TR.GrossProfit."""
    from lseg.data.content import fundamental_and_reference

    universe = _require_non_empty("universe", universe)
    fields = _require_non_empty("fields", fields)
    definition = fundamental_and_reference.Definition(
        universe=universe, fields=fields, parameters=parameters
    )
    response = definition.get_data(session=session)
    try:
        return _ensure_frame(response.data.df, "fundamentals")
    finally:
        close_quietly(response)


def get_news_headlines(
    query: str,
    count: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_order: str = "newToOld",
    session: Any | None = None,
) -> pd.DataFrame:
    """News headlines matching an RQL query, e.g. `'IBM.N AND Language:EN'`."""
    from lseg.data.content.news import headlines

    if not query or not query.strip():
        raise ValueError("'query' must be a non-empty news query.")
    definition = headlines.Definition(
        query=query,
        count=count,
        date_from=date_from,
        date_to=date_to,
        sort_order=sort_order,
    )
    response = definition.get_data(session=session)
    try:
        return _ensure_frame(response.data.df, "news headlines")
    finally:
        close_quietly(response)


def search_instruments(
    query: str,
    view: str = "SearchAll",
    top: int = 10,
    session: Any | None = None,
) -> pd.DataFrame:
    """Discovery search: resolve names/text to RICs and metadata."""
    from lseg.data.content import search

    if not query or not query.strip():
        raise ValueError("'query' must be a non-empty search string.")
    definition = search.Definition(query=query, view=view, top=top)
    response = definition.get_data(session=session)
    try:
        return _ensure_frame(response.data.df, "search")
    finally:
        close_quietly(response)


def _ensure_frame(df: Any, what: str) -> pd.DataFrame:
    if df is None or (hasattr(df, "empty") and df.empty):
        raise RuntimeError(f"LSEG returned no {what} data (empty DataFrame).")
    return df


def close_quietly(response: Any) -> None:
    try:
        response.close()
    except Exception:  # noqa: BLE001, S110 — best-effort cleanup
        pass
