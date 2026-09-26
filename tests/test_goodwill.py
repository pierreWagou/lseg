"""Goodwill module tests — LSEG is mocked, no network/credentials."""

import pandas as pd
import pytest

from lseg_extractor import goodwill
from lseg_extractor.cli import _coerce_date
from lseg_extractor.goodwill import (
    FRENCH_SCREENER,
    GOODWILL_FIELD,
    get_goodwill_history,
    load_french_universe,
    to_tidy_goodwill,
)


def _access_frame() -> pd.DataFrame:
    """Mimic ld.get_data output for history params: one row per (RIC, year)."""
    return pd.DataFrame(
        {
            "Instrument": ["TTE.PA", "TTE.PA", "MC.PA"],
            "Company Common Name": ["TOTALENERGIES", "TOTALENERGIES", "LVMH"],
            "Goodwill": [1000.0, 1100.0, float("nan")],
            "Period End Date": ["2022-12-31", "2023-12-31", "2023-12-31"],
            "FPeriod": ["FY2022", "FY2023", "FY2023"],
        }
    )


def test_load_cac40_preset_has_40_rics() -> None:
    rics = load_french_universe("cac40")
    assert len(rics) == 40
    assert "TTE.PA" in rics and "MC.PA" in rics


def test_load_all_france_returns_screener() -> None:
    assert load_french_universe("all-france") == [FRENCH_SCREENER]


def test_load_unknown_preset_raises() -> None:
    with pytest.raises(ValueError, match="unknown preset"):
        load_french_universe("dax")


def test_to_tidy_access_frame() -> None:
    tidy = to_tidy_goodwill(_access_frame(), currency="EUR")
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
    assert tidy["fiscal_year"].tolist() == [2022, 2023, 2023]
    assert tidy["fiscal_period"].tolist() == ["FY2022", "FY2023", "FY2023"]
    assert (tidy["currency"] == "EUR").all()
    assert (tidy["source_field"] == GOODWILL_FIELD).all()
    assert tidy["goodwill"].isna().sum() == 1  # NA rows preserved


def test_to_tidy_missing_goodwill_column_raises() -> None:
    df = pd.DataFrame({"Instrument": ["TTE.PA"], "BID": [1.0]})
    # Single requested value field that is NOT among helpers: BID columns are its series.
    tidy = to_tidy_goodwill(df, fields=["BID"])
    assert tidy["goodwill"].tolist() == [1.0]
    assert tidy["source_field"].tolist() == ["BID"]


def test_to_tidy_single_field_ignores_header_names() -> None:
    # Live shape: value columns titled by year, no "goodwill" header anywhere.
    df = pd.DataFrame(
        {
            "Instrument": ["TTE.PA"],
            "Company Common Name": ["TOTALENERGIES"],
            "2022": [1000.0],
            "2023": [1100.0],
        }
    )
    tidy = to_tidy_goodwill(df, fields=[GOODWILL_FIELD])
    assert len(tidy) == 2
    assert tidy["fiscal_year"].tolist() == [2022, 2023]
    assert tidy["goodwill"].tolist() == [1000.0, 1100.0]
    assert (tidy["source_field"] == GOODWILL_FIELD).all()


def test_to_tidy_multi_field_unmatched_raises() -> None:
    df = pd.DataFrame({"Instrument": ["TTE.PA"], "BID": [1.0]})
    with pytest.raises(RuntimeError, match="No column for requested field"):
        to_tidy_goodwill(df, fields=["TR.Goodwill", "TR.Revenue"])


def test_get_goodwill_history_batches_and_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_get_snapshot(universe, fields, parameters=None, session=None):  # type: ignore[no-untyped-def]
        calls.append({"universe": list(universe), "fields": fields, "parameters": parameters})
        idx = [f"RIC{i}.PA" for i in range(len(universe))]
        return pd.DataFrame(
            {
                "Instrument": idx,
                "Company Common Name": idx,
                "Goodwill": [1.0] * len(universe),
                "Period End Date": ["2023-12-31"] * len(universe),
                "FPeriod": ["FY2023"] * len(universe),
            }
        )

    monkeypatch.setattr(goodwill, "get_snapshot", fake_get_snapshot)
    tidy = get_goodwill_history(
        [f"RIC{i}.PA" for i in range(120)],
        years=3,
        start_year=2023,
        end_year=2023,
        batch_size=50,
        pause=0,
    )
    assert len(tidy) == 120
    assert len(calls) == 3  # 50 / 50 / 20
    params = calls[0]["parameters"]
    assert params == {"Period": "FY0", "Frq": "FY", "SDate": 0, "EDate": -3, "Curn": "EUR"}
    assert GOODWILL_FIELD in calls[0]["fields"]


def test_get_goodwill_history_screener_sent_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list = []

    def fake_get_snapshot(universe, fields, parameters=None, session=None):  # type: ignore[no-untyped-def]
        seen.append(list(universe))
        return _access_frame()

    monkeypatch.setattr(goodwill, "get_snapshot", fake_get_snapshot)
    tidy = get_goodwill_history("all-france", years=5, pause=0)
    assert seen == [[FRENCH_SCREENER]]  # never split into batches
    assert set(tidy["ric"]) == {"TTE.PA", "MC.PA"}


def test_get_goodwill_history_sdate_edate_forms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list = []

    def fake_get_snapshot(universe, fields, parameters=None, session=None):  # type: ignore[no-untyped-def]
        seen.append(parameters)
        return pd.DataFrame(
            {
                "Instrument": ["TTE.PA"],
                "Goodwill": [1.0],
                "Period End Date": ["2023-12-31"],
            }
        )

    monkeypatch.setattr(goodwill, "get_snapshot", fake_get_snapshot)
    get_goodwill_history(["TTE.PA"], years=3, pause=0)
    assert seen[0]["SDate"] == 0 and seen[0]["EDate"] == -3
    # Official string forms pass through untouched.
    get_goodwill_history(["TTE.PA"], years=3, sdate="0CY", edate="-1AM", pause=0)
    assert seen[1]["SDate"] == "0CY" and seen[1]["EDate"] == "-1AM"


def test_get_goodwill_history_year_filter_empties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        goodwill,
        "get_snapshot",
        lambda *a, **kw: _access_frame(),  # type: ignore[no-untyped-def]
    )
    with pytest.raises(RuntimeError, match="year filtering"):
        get_goodwill_history(["TTE.PA"], years=5, start_year=2030, pause=0)


def test_coerce_date() -> None:
    assert _coerce_date(None, -5) == -5
    assert _coerce_date("-35", -5) == -35
    assert _coerce_date("0CY", 0) == "0CY"
    assert _coerce_date("-1AM", -5) == "-1AM"


def test_get_goodwill_history_rejects_empty_universe() -> None:
    with pytest.raises(ValueError, match="universe"):
        get_goodwill_history([], years=5)


def test_get_goodwill_history_rejects_bad_years() -> None:
    with pytest.raises(ValueError, match="years"):
        get_goodwill_history(["TTE.PA"], years=0)
