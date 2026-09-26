"""Goodwill history for French companies — reusable core (no I/O, no CLI).

Import-safe for CLI, REST API, or frontend backends. Returns tidy long-form
`pandas.DataFrame` with one row per (company, fiscal period).

Field/parameter names are UNCONFIRMED live (see `docs/goodwill-fields.md`):
everything lives in the module constants below so confirmation is a 1-line change.
"""

from importlib.resources import files as _resources_files
from pathlib import Path
from typing import Any

import pandas as pd

from lseg_extractor.client import get_fundamentals

# --- Single-change-point constants (see docs/goodwill-fields.md) ---
GOODWILL_FIELD = "TR.Goodwill"
"""Primary TR data item for balance-sheet net carrying goodwill (IFRS 3)."""

FRENCH_PRESETS = ("cac40", "sbf120")
"""Available `--preset` values, bundled under `lseg_extractor/data/universes/`."""

_HISTORY_PARAM_DEFAULTS = {"Frq": "FY"}
"""Non-date history params merged into every goodwill request."""

_CHUNK_SIZE = 10
"""RICs per underlying request (keeps request URLs small)."""

__all__ = [
    "FRENCH_PRESETS",
    "GOODWILL_FIELD",
    "get_goodwill_history",
    "load_french_universe",
    "to_tidy_goodwill",
]


def load_french_universe(preset: str) -> list[str]:
    """Load a French preset universe (e.g. `cac40`) → list of RICs."""
    preset = preset.strip().lower()
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
    universe: list[str] | str,
    years: int = 5,
    fields: list[str] | None = None,
    currency: str = "EUR",
    parameters: dict | None = None,
    session: Any | None = None,
) -> pd.DataFrame:
    """Annual goodwill carrying values per company, tidy long form.

    Args:
        universe: RIC list, `@file.txt`, or preset name (`cac40`/`sbf120`).
        years: number of annual fiscal periods (`Frq=FY`).
        fields: TR goodwill fields (default `[GOODWILL_FIELD]`).
        currency: `Curn` conversion target (default EUR for French groups).
        parameters: override/extend auto-built history params.
        session: optional open LSEG session (passed to `get_fundamentals`).

    Returns:
        DataFrame with columns
        `ric, company_name, fiscal_period, fiscal_year, goodwill, currency, source_field`.
        Missing company/years are kept as `NA` rows so coverage gaps stay visible.
    """
    rics = _resolve_universe(universe)
    if years < 1:
        raise ValueError("'years' must be >= 1.")
    fields = fields or [GOODWILL_FIELD]
    params = {"SDate": f"-{years}Y", "EDate": "0D", "Curn": currency, **_HISTORY_PARAM_DEFAULTS}
    if parameters:
        params.update(parameters)

    frames: list[pd.DataFrame] = []
    for i in range(0, len(rics), _CHUNK_SIZE):
        chunk = rics[i : i + _CHUNK_SIZE]
        wide = get_fundamentals(chunk, fields, parameters=params, session=session)
        frames.append(to_tidy_goodwill(wide, fields=fields, currency=currency))
    tidy = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if tidy.empty:
        raise RuntimeError("LSEG returned no goodwill data (empty DataFrame).")
    return tidy


def to_tidy_goodwill(
    df: pd.DataFrame,
    fields: list[str] | None = None,
    currency: str = "EUR",
) -> pd.DataFrame:
    """Normalize a fundamentals response to tidy goodwill long form.

    Handles wide responses (periods as columns, possibly MultiIndex
    field×period) and already-long frames. Never drops NA values.
    """
    fields = fields or [GOODWILL_FIELD]
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "ric",
                "company_name",
                "fiscal_period",
                "fiscal_year",
                "goodwill",
                "currency",
                "source_field",
            ]
        )

    index_names = [n for n in (df.index.names or []) if n]
    id_cols = [
        c for c in df.reset_index().columns if c in ("Instrument", "RIC", "instrument", "ric")
    ]
    frame = df.reset_index()
    ric_col = id_cols[0] if id_cols else (index_names[0] if index_names else frame.columns[0])
    name_col = next(
        (c for c in frame.columns if str(c).lower() in ("company name", "companyname", "name")),
        None,
    )

    value_cols = [c for c in frame.columns if c not in {ric_col, name_col}]
    if isinstance(df.columns, pd.MultiIndex):
        # field × period layout → stack periods, keep goodwill fields only.
        stacked = df.stack(level=list(range(1, df.columns.nlevels)), future_stack=True)
        stacked = stacked.reset_index()
        period_col = stacked.columns[1]
        goodwill_cols = [c for c in stacked.columns[2:] if str(c) in fields]
        if not goodwill_cols:
            goodwill_cols = list(stacked.columns[2:])
        long = stacked.melt(
            id_vars=[stacked.columns[0], period_col],
            value_vars=goodwill_cols,
            var_name="source_field",
            value_name="goodwill",
        )
        long = long.rename(columns={stacked.columns[0]: "ric", period_col: "fiscal_period"})
        long["company_name"] = pd.NA
    else:
        long = frame.melt(
            id_vars=[c for c in [ric_col, name_col] if c is not None],
            value_vars=value_cols,
            var_name="fiscal_period",
            value_name="goodwill",
        )
        long = long.rename(columns={ric_col: "ric"})
        if name_col:
            long = long.rename(columns={name_col: "company_name"})
        else:
            long["company_name"] = pd.NA
        long["source_field"] = (
            fields[0] if len(fields) == 1 else long["fiscal_period"].map(lambda _p: fields[0])
        )

    long["fiscal_period"] = long["fiscal_period"].astype(str)
    long["fiscal_year"] = long["fiscal_period"].str.extract(r"(\d{4})").astype("Int64")
    long["currency"] = currency
    long["goodwill"] = pd.to_numeric(long["goodwill"], errors="coerce")
    return long[
        [
            "ric",
            "company_name",
            "fiscal_period",
            "fiscal_year",
            "goodwill",
            "currency",
            "source_field",
        ]
    ]


def _resolve_universe(universe: list[str] | str) -> list[str]:
    if isinstance(universe, str):
        text = universe.strip()
        if text.startswith("@"):
            path = Path(text[1:])
            if not path.exists():
                # allow @preset shorthand
                return load_french_universe(text[1:])
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
    rics = [r.strip() for r in items if r and r.strip()]
    if not rics:
        raise ValueError("'universe' must contain at least one RIC or preset.")
    return rics


def _preset_path(preset: str) -> Path:
    # 1) packaged data (installed distribution), 2) legacy repo-root data/.
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
