"""Goodwill module tests — LSEG is mocked, no network/credentials."""

import pandas as pd
import pytest

from lseg_extractor import goodwill
from lseg_extractor.goodwill import (
    GOODWILL_FIELD,
    get_goodwill_history,
    load_french_universe,
    to_tidy_goodwill,
)


def _wide_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"2022": [1_000.0], "2023": [1_100.0], "2024": [1_250.0]},
        index=pd.Index(["TTE.PA"], name="Instrument"),
    )


def test_load_cac40_preset_has_40_rics() -> None:
    rics = load_french_universe("cac40")
    assert len(rics) == 40
    assert "TTE.PA" in rics and "MC.PA" in rics


def test_load_unknown_preset_raises() -> None:
    with pytest.raises(ValueError, match="unknown preset"):
        load_french_universe("dax")


def test_to_tidy_wide_frame() -> None:
    tidy = to_tidy_goodwill(_wide_frame(), fields=[GOODWILL_FIELD], currency="EUR")
    assert list(tidy.columns) == [
        "ric",
        "company_name",
        "fiscal_period",
        "fiscal_year",
        "goodwill",
        "currency",
        "source_field",
    ]
    assert len(tidy) == 3
    assert tidy["fiscal_year"].tolist() == [2022, 2023, 2024]
    assert (tidy["currency"] == "EUR").all()
    assert (tidy["source_field"] == GOODWILL_FIELD).all()


def test_to_tidy_keeps_na_rows() -> None:
    df = pd.DataFrame({"2024": [float("nan")]}, index=pd.Index(["ALO.PA"], name="Instrument"))
    tidy = to_tidy_goodwill(df)
    assert len(tidy) == 1 and tidy["goodwill"].isna().all()


def test_get_goodwill_history_chunks_and_concatenates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_get_fundamentals(universe, fields, parameters=None, session=None):  # type: ignore[no-untyped-def]
        calls.append({"universe": list(universe), "parameters": parameters})
        idx = pd.Index(universe, name="Instrument")
        return pd.DataFrame({"2024": [1.0] * len(universe)}, index=idx)

    monkeypatch.setattr(goodwill, "get_fundamentals", fake_get_fundamentals)
    tidy = get_goodwill_history([f"RIC{i}.PA" for i in range(25)], years=3)
    assert len(tidy) == 25  # 25 RICs × 1 period column
    assert len(calls) == 3  # chunked 10 / 10 / 5
    assert calls[0]["parameters"]["SDate"] == "-3Y"
    assert calls[0]["parameters"]["Frq"] == "FY"
    assert calls[0]["parameters"]["Curn"] == "EUR"


def test_get_goodwill_history_rejects_empty_universe() -> None:
    with pytest.raises(ValueError, match="universe"):
        get_goodwill_history([], years=5)


def test_get_goodwill_history_rejects_bad_years() -> None:
    with pytest.raises(ValueError, match="years"):
        get_goodwill_history(["TTE.PA"], years=0)
