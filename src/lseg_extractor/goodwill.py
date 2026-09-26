"""Goodwill history for French companies — reusable core (no I/O, no CLI).

Import-safe for CLI, REST API, or frontend backends. Returns tidy long-form
`pandas.DataFrame` with one row per (company, fiscal year).

Live-confirmed pattern (Workspace session): Access-layer `ld.get_data` with
`TR.Goodwill` + `{\"Period\": \"FY0\", \"Frq\": \"FY\", \"SDate\": 0, \"EDate\": -N,
\"Curn\": \"EUR\"}`. See `docs/goodwill-fields.md`.
"""

import time
from importlib.resources import files as _resources_files
from pathlib import Path
from typing import Any

import pandas as pd

from lseg_extractor.client import get_snapshot

# --- Change-point constants (see docs/goodwill-fields.md) ---
GOODWILL_FIELD = "TR.Goodwill"
"""TR data item for balance-sheet net carrying goodwill (IFRS 3)."""

PERIOD_END_FIELD = "TR.F.PeriodEndDate"
"""Fiscal close date, used to derive the accounting year."""

PERIOD_LABEL_FIELD = "TR.F.PeriodEndDate.fperiod"
"""Fiscal period label, e.g. `FY2024`."""

COMPANY_NAME_FIELD = "TR.CommonName"

FRENCH_SCREENER = (
    'SCREEN(U(IN(Equity(active or inactive,public,primary))),IN(TR.HQCountryCode,"FR"),CURN=EUR)'
)
"""All French listed companies (active or inactive), euro-converted."""

FRENCH_PRESETS = ("cac40", "sbf120", "all-france")
"""Available `--preset` values (`all-france` = screener above)."""

_BATCH_SIZE = 50
_BATCH_PAUSE_SECS = 0.5

__all__ = [
    "COMPANY_NAME_FIELD",
    "FRENCH_PRESETS",
    "FRENCH_SCREENER",
    "GOODWILL_FIELD",
    "PERIOD_END_FIELD",
    "PERIOD_LABEL_FIELD",
    "get_goodwill_history",
    "load_french_universe",
    "to_tidy_goodwill",
]


def load_french_universe(preset: str) -> list[str]:
    """Load a French file-based preset universe (e.g. `cac40`) → RIC list."""
    preset = preset.strip().lower()
    if preset == "all-france":
        return [FRENCH_SCREENER]
    if preset not in FRENCH_PRESETS:
        raise ValueError(f"unknown preset {preset!r}; choose from {list(FRENCH_PRESETS)}.")
    path = _preset_path(preset)
    if not path.exists():
        raise FileNotFoundError(f"universe file not found: {path}")
    rics = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not rics:
        raise ValueError(f"universe file is empty: {path}")
    return rics


def get_goodwill_history(
    universe: list[str] | str = "cac40",
    years: int = 5,
    start_year: int | None = None,
    end_year: int | None = None,
    fields: list[str] | None = None,
    currency: str = "EUR",
    parameters: dict | None = None,
    batch_size: int = _BATCH_SIZE,
    pause: float = _BATCH_PAUSE_SECS,
    session: Any | None = None,
) -> pd.DataFrame:
    """Annual goodwill carrying values per company, tidy long form.

    Args:
        universe: preset (`cac40`/`sbf120`/`all-france`), `@file.txt`,
            comma-separated RICs, RIC list, or raw `SCREEN(...)` expression.
        years: annual fiscal periods back from today (`EDate=-years`).
        start_year/end_year: keep fiscal years in `[start_year, end_year]`.
        fields: TR fields (default goodwill + period-end helpers).
        currency: `Curn` conversion target (default EUR).
        parameters: override/extend auto-built history params.
        batch_size/pause: throttle large universes (screener extracts).
        session: accepted for signature uniformity (unused, see noqa).

    Returns:
        DataFrame with columns
        `ric, company_name, fiscal_period, fiscal_year, goodwill, currency, source_field`.
        Missing company/years are kept as `NA` rows so coverage gaps stay visible.
    """
    units = _resolve_universe(universe)
    if years < 1:
        raise ValueError("'years' must be >= 1.")
    if batch_size < 1:
        raise ValueError("'batch_size' must be >= 1.")
    fields = fields or [COMPANY_NAME_FIELD, GOODWILL_FIELD, PERIOD_END_FIELD, PERIOD_LABEL_FIELD]
    params = {"Period": "FY0", "Frq": "FY", "SDate": 0, "EDate": -years, "Curn": currency}
    if parameters:
        params.update(parameters)

    frames: list[pd.DataFrame] = []
    batches = _to_batches(units, batch_size)
    for i, batch in enumerate(batches):
        wide = get_snapshot(batch, fields, parameters=params)
        frames.append(to_tidy_goodwill(wide, currency=currency))
        if pause > 0 and i < len(batches) - 1:
            time.sleep(pause)
    tidy = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if tidy.empty:
        raise RuntimeError("LSEG returned no goodwill data (empty DataFrame).")
    if start_year is not None:
        tidy = tidy[tidy["fiscal_year"].fillna(-1) >= start_year]
    if end_year is not None:
        tidy = tidy[tidy["fiscal_year"].fillna(10**9) <= end_year]
    tidy = tidy.sort_values(by=["ric", "fiscal_year"]).reset_index(drop=True)
    if tidy.empty:
        raise RuntimeError("No goodwill rows left after year filtering.")
    return tidy


def to_tidy_goodwill(df: pd.DataFrame, currency: str = "EUR") -> pd.DataFrame:
    """Normalize an Access-layer goodwill response to tidy long form.

    Expected columns (matched case-insensitively, header wording may vary by
    library version): instrument id, company name, a goodwill value column, a
    period-end date column, and optionally an fperiod label column.
    Never drops NA values.
    """
    columns = [
        "ric",
        "company_name",
        "fiscal_period",
        "fiscal_year",
        "goodwill",
        "currency",
        "source_field",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)

    frame = df.reset_index()
    cols = {str(c).upper(): c for c in frame.columns}

    def _find(*needles: str, exclude: str = "") -> str | None:
        for upper, original in cols.items():
            if exclude and exclude in upper:
                continue
            if any(n in upper for n in needles):
                return original
        return None

    ric_col = _find("INSTRUMENT", "RIC") or frame.columns[0]
    name_col = _find("COMMONNAME", "COMMON NAME", "COMPANYNAME", "COMPANY NAME", "NAME")
    gw_col = _find("GOODWILL")
    date_col = _find("PERIODENDDATE", "PERIOD END", exclude="FPERIOD")
    label_col = _find("FPERIOD")
    if gw_col is None:
        raise RuntimeError(
            f"No goodwill column in LSEG response. Got columns: {list(frame.columns)}"
        )

    out = pd.DataFrame()
    out["ric"] = frame[ric_col].astype(str)
    out["company_name"] = frame[name_col].astype(str) if name_col else pd.NA
    if label_col:
        out["fiscal_period"] = frame[label_col].astype(str)
    elif date_col:
        out["fiscal_period"] = frame[date_col].astype(str)
    else:
        out["fiscal_period"] = pd.NA
    if date_col:
        dates = pd.to_datetime(frame[date_col], errors="coerce")
        out["fiscal_year"] = dates.dt.year.astype("Int64")
    else:
        out["fiscal_year"] = (
            out["fiscal_period"].astype(str).str.extract(r"(\d{4})").astype("Int64")
        )
    out["goodwill"] = pd.to_numeric(frame[gw_col], errors="coerce")
    out["currency"] = currency
    out["source_field"] = GOODWILL_FIELD
    return out[columns]


def _resolve_universe(universe: list[str] | str) -> list[str]:
    if isinstance(universe, str):
        text = universe.strip()
        if text.upper().startswith("SCREEN("):
            return [text]  # raw screener expression: single unit, never split
        if text.startswith("@"):
            path = Path(text[1:])
            if not path.exists():
                return load_french_universe(text[1:])  # @preset shorthand
            items = [
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        elif text.lower() in FRENCH_PRESETS:
            return load_french_universe(text)
        else:
            items = [p.strip() for p in text.split(",")]
    else:
        items = list(universe)
    units = [u.strip() for u in items if u and u.strip()]
    if not units:
        raise ValueError("'universe' must contain at least one RIC, preset, or SCREEN().")
    return units


def _to_batches(units: list[str], batch_size: int) -> list[list[str]]:
    if len(units) == 1 and units[0].upper().startswith("SCREEN("):
        return [units]  # screener resolves server-side; send whole
    return [units[i : i + batch_size] for i in range(0, len(units), batch_size)]


def _preset_path(preset: str) -> Path:
    # 1) packaged data (installed distribution), 2) sibling data dir.
    try:
        candidate = _resources_files("lseg_extractor") / "data" / "universes" / f"{preset}.txt"
        if candidate.is_file():
            return Path(str(candidate))
    except Exception:  # noqa: BLE001, S110 — fall back to sibling data dir
        pass
    sibling = Path(__file__).resolve().parent / "data" / "universes" / f"{preset}.txt"
    if sibling.exists():
        return sibling
    return Path(__file__).resolve().parents[2] / "data" / "universes" / f"{preset}.txt"
