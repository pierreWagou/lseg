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
    sdate: int | str = 0,
    edate: int | str | None = None,
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
        sdate/edate: `SDate`/`EDate` values. Defaults `0`/`-years` (integer
            relative offsets, colleague-proven). Official docs attest string
            forms instead (e.g. `'0CY'`, `'2020-01-01'`, `'-1AM'`) — pass
            strings here to try those without code changes.
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
    params = {
        "Period": "FY0",
        "Frq": "FY",
        "SDate": sdate,
        "EDate": -years if edate is None else edate,
        "Curn": currency,
    }
    if parameters:
        params.update(parameters)

    frames: list[pd.DataFrame] = []
    batches = _to_batches(units, batch_size)
    for i, batch in enumerate(batches):
        wide = get_snapshot(batch, fields, parameters=params)
        frames.append(to_tidy_goodwill(wide, fields=fields, currency=currency))
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


def to_tidy_goodwill(
    df: pd.DataFrame,
    fields: list[str] | None = None,
    currency: str = "EUR",
) -> pd.DataFrame:
    """Normalize an Access-layer goodwill response to tidy long form.

    Column headers vary by library version (titles vs field names, localized
    display names), so matching is case-insensitive and structural:

    - Helper columns (instrument id, company name, period-end date, fperiod
      label) are identified by name.
    - When exactly one non-helper field was requested (the normal
      single-`TR.Goodwill` path), **all remaining columns are its series by
      construction** — no \"GOODWILL\" header required.
    - With several value fields, columns are matched per field and anything
      unmatched raises an error listing the actual columns.

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
    fields = fields or [GOODWILL_FIELD]

    frame = df.reset_index()
    cols = {str(c).upper(): c for c in frame.columns}

    def _find(*needles: str, exclude: str = "") -> str | None:
        for upper, original in cols.items():
            if exclude and exclude in upper:
                continue
            if any(n in upper for n in needles):
                return original
        return None

    helpers: set = {
        _find("INSTRUMENT", "RIC")
        or next((c for c in frame.columns if c in df.columns), frame.columns[0]),
        _find("COMMONNAME", "COMMON NAME", "COMPANYNAME", "COMPANY NAME", "NAME"),
        _find("PERIODENDDATE", "PERIOD END", exclude="FPERIOD"),
        _find("FPERIOD"),
    }
    helpers.discard(None)
    # Columns created by reset_index() itself (e.g. "index") are structural,
    # never value columns.
    helpers.update(c for c in frame.columns if c not in df.columns)
    ric_col = _find("INSTRUMENT", "RIC") or next(
        (c for c in frame.columns if c in df.columns), frame.columns[0]
    )
    name_col = _find("COMMONNAME", "COMMON NAME", "COMPANYNAME", "COMPANY NAME", "NAME")
    date_col = _find("PERIODENDDATE", "PERIOD END", exclude="FPERIOD")
    label_col = _find("FPERIOD")

    helper_fields = {
        COMPANY_NAME_FIELD.upper(),
        PERIOD_END_FIELD.upper(),
        PERIOD_LABEL_FIELD.upper(),
    }
    value_fields = [f for f in fields if f.upper() not in helper_fields]
    if not value_fields:
        raise RuntimeError(f"No value field requested. Got columns: {list(frame.columns)}")

    if len(value_fields) == 1:
        # Single requested field: remaining columns ARE its series.
        value_cols = [c for c in frame.columns if c not in helpers]
        if not value_cols:
            raise RuntimeError(
                f"No value columns in LSEG response. Got columns: {list(frame.columns)}"
            )
        long = frame.melt(
            id_vars=sorted(helpers, key=list(frame.columns).index),
            value_vars=value_cols,
            var_name="_period",
            value_name="goodwill",
        )
        long["source_field"] = value_fields[0]
    else:
        # Several value fields: match columns per field suffix, e.g. "Goodwill".
        parts: list[pd.DataFrame] = []
        for field in value_fields:
            suffix = field.split(".")[-1].upper()
            matched = [c for c in frame.columns if c not in helpers and suffix in str(c).upper()]
            if not matched:
                raise RuntimeError(
                    f"No column for requested field {field!r}. Got columns: {list(frame.columns)}"
                )
            part = frame.melt(
                id_vars=sorted(helpers, key=list(frame.columns).index),
                value_vars=matched,
                var_name="_period",
                value_name="goodwill",
            )
            part["source_field"] = field
            parts.append(part)
        long = pd.concat(parts, ignore_index=True)

    long = long.rename(columns={ric_col: "ric"})
    long["company_name"] = (
        long[name_col].astype(str) if name_col and name_col in long.columns else pd.NA
    )
    if label_col and label_col in long.columns:
        long["fiscal_period"] = long[label_col].astype(str)
    elif date_col and date_col in long.columns:
        long["fiscal_period"] = long[date_col].astype(str)
    else:
        long["fiscal_period"] = long["_period"].astype(str)
    if date_col and date_col in long.columns:
        dates = pd.to_datetime(long[date_col], errors="coerce")
        long["fiscal_year"] = dates.dt.year.astype("Int64")
    else:
        long["fiscal_year"] = (
            long["fiscal_period"].astype(str).str.extract(r"(\d{4})").astype("Int64")
        )
    long["goodwill"] = pd.to_numeric(long["goodwill"], errors="coerce")
    long["currency"] = currency
    return long[columns]


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
