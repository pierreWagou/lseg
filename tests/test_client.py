"""Client primitive tests — lseg.data is mocked, no network."""

from types import SimpleNamespace

import lseg.data as ld
import pandas as pd
import pytest

from lseg_extractor.client import (
    get_esg_measures,
    get_esg_overview,
    get_fundamentals,
    get_history,
    get_news_headlines,
    get_snapshot,
    search_instruments,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"BID": [1.0], "ASK": [1.1]}, index=["IBM.N"])


def test_get_snapshot_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ld, "get_data", lambda **kw: _frame())
    df = get_snapshot(["IBM.N"], ["BID", "ASK"])
    assert list(df.columns) == ["BID", "ASK"]


def test_get_snapshot_rejects_empty_universe() -> None:
    with pytest.raises(ValueError, match="universe"):
        get_snapshot([], ["BID"])


def test_get_snapshot_empty_frame_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ld, "get_data", lambda **kw: pd.DataFrame())
    with pytest.raises(RuntimeError, match="no snapshot"):
        get_snapshot(["IBM.N"], ["BID"])


def test_get_history_forwards_params(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    expected = pd.DataFrame({"CLOSE": [100.0]})

    def fake_history(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(ld, "get_history", fake_history)
    df = get_history(["TRI.N"], interval="1D", start="2024-01-01", count=5)
    assert df is expected
    assert captured["interval"] == "1D"
    assert captured["start"] == "2024-01-01"
    assert captured["count"] == 5


def _patch_content_definition(
    monkeypatch: pytest.MonkeyPatch, module_path: str, df: pd.DataFrame
) -> dict:
    """Patch a content Definition to return a fake response; return captured kwargs."""
    import importlib

    captured: dict = {}
    mod = importlib.import_module(module_path)

    class FakeDefinition:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)

        def get_data(self, session=None):  # type: ignore[no-untyped-def]
            return SimpleNamespace(data=SimpleNamespace(df=df), close=lambda: None)

    monkeypatch.setattr(mod, "Definition", FakeDefinition)
    return captured


def test_get_fundamentals(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_content_definition(
        monkeypatch, "lseg.data.content.fundamental_and_reference", _frame()
    )
    df = get_fundamentals(["TRI.N"], ["TR.Revenue"])
    assert not df.empty
    assert captured["universe"] == ["TRI.N"]


def test_get_news_headlines_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query"):
        get_news_headlines("  ")


def test_get_news_headlines(monkeypatch: pytest.MonkeyPatch) -> None:
    news_df = pd.DataFrame({"Title": ["hello"]})
    _patch_content_definition(monkeypatch, "lseg.data.content.news.headlines", news_df)
    df = get_news_headlines("IBM.N AND Language:EN", count=5)
    assert df is news_df


def test_search_instruments(monkeypatch: pytest.MonkeyPatch) -> None:
    search_df = pd.DataFrame({"RIC": ["IBM.N"]})
    captured = _patch_content_definition(monkeypatch, "lseg.data.content.search", search_df)
    df = search_instruments("IBM", top=3)
    assert df is search_df
    assert captured["top"] == 3


def test_get_esg_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    esg_df = pd.DataFrame({"ESG Score": [75.5]}, index=["TTE.PA"])
    captured = _patch_content_definition(
        monkeypatch, "lseg.data.content.esg.basic_overview", esg_df
    )
    df = get_esg_overview(["TTE.PA"])
    assert df is esg_df
    assert captured["universe"] == ["TTE.PA"]


def test_get_esg_overview_rejects_empty_universe() -> None:
    with pytest.raises(ValueError, match="universe"):
        get_esg_overview([])


def test_get_esg_measures_forwards_years(monkeypatch: pytest.MonkeyPatch) -> None:
    esg_df = pd.DataFrame({"ESG Score": [75.5]})
    captured = _patch_content_definition(
        monkeypatch, "lseg.data.content.esg.standard_measures", esg_df
    )
    df = get_esg_measures(["TTE.PA"], start=2020, end=2024)
    assert df is esg_df
    assert captured == {"universe": ["TTE.PA"], "start": 2020, "end": 2024}


def test_get_esg_measures_empty_frame_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_content_definition(
        monkeypatch, "lseg.data.content.esg.standard_measures", pd.DataFrame()
    )
    with pytest.raises(RuntimeError, match="no ESG measures"):
        get_esg_measures(["TTE.PA"])
