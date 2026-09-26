# lseg-extractor

Extract market, reference, and news data from the **LSEG Data Platform** via the
[`lseg-data`](https://pypi.org/project/lseg-data/) library (v2).

Layered design: **reusable core** (`src/lseg_extractor/client.py`) usable from a
CLI, REST API, or frontend backend, plus a **thin CLI** (`lseg-extract`) on top.

## Setup

Requires `uv` and Python 3.11+ (pinned to 3.12 via `.python-version`).

```bash
uv sync --group dev
uv run python -c "import lseg.data as ld; print('ok')"
```

## Authentication (dual mode)

| Mode | When to use | What you need |
|---|---|---|
| `desktop` (local dev default) | LSEG Workspace / Eikon already open on this machine | AppKey only (`LSEG_APP_KEY`); app listens on port 9000+ |
| `platform-ldpv2` (headless) | Servers, CI, REST backends, no desktop | AppKey + service `client_id` + `client_secret` (OAuth2 client credentials) |

Hybrid secrets approach (why not secrets-in-JSON):

- `lseg-data.config.json` is **committed as a placeholder template** (session
  default, log config) — never real secrets. LSEG docs themselves warn against
  hardcoding creds and offer a `.env` alternative (`QS_1.0 - Sessions`).
- Real secrets live only in **env / `.env`** (git-ignored, 12-factor, works in
  Docker/CI/secret managers).
- `session.py` builds the session **explicitly in code**
  (`ld.session.desktop/desktop` vs `ld.session.platform.Definition` +
  `ClientCredentials`), falling back to `ld.open_session()` (config file) when
  no env secrets are set. One code path for CLI, API, and frontend.

```bash
cp .env.example .env
# Desktop: LSEG_SESSION=desktop + LSEG_APP_KEY=...
# Headless: LSEG_SESSION=platform-ldpv2 + LSEG_APP_KEY/LSEG_CLIENT_ID/LSEG_CLIENT_SECRET
```

`LSEG_SESSION=auto` (default) picks headless when full credentials exist,
otherwise desktop.

## CLI usage

```bash
# Pricing snapshot (Access layer ld.get_data)
uv run lseg-extract snapshot --universe "IBM.N,VOD.L" --fields "BID,ASK,TR.Revenue"

# Historical series (Access layer ld.get_history)
uv run lseg-extract history --universe "TRI.N" --interval 1D --start 2024-01-01 --count 10

# Fundamentals & reference (Content layer)
uv run lseg-extract fundamentals --universe "TRI.N,IBM.N" --fields "TR.Revenue,TR.GrossProfit"

# News headlines
uv run lseg-extract news --query "IBM.N AND Language:EN" --count 5

# Discovery search (names → RICs)
uv run lseg-extract search --query "Apple" --top 5

# Write to file (CSV default, or --format parquet)
uv run lseg-extract snapshot --universe "IBM.N" --fields "BID,ASK" --output out.csv
uv run lseg-extract history --universe "TRI.N" --output hist.parquet --format parquet

# Universe/fields from file (one per line, # comments allowed)
uv run lseg-extract snapshot --universe @rics.txt --fields @fields.txt
```

## Goodwill history (French companies)

Balance-sheet net carrying goodwill (IFRS 3), annual multi-year history, tidy
long form (`ric, company_name, fiscal_period, fiscal_year, goodwill, currency,
source_field`). Uses the Access layer: `TR.Goodwill` + `TR.F.PeriodEndDate` /
`.fperiod`, params `Period=FY0, Frq=FY, SDate=0, EDate=-N, Curn=EUR`
(see `docs/goodwill-fields.md`).

```bash
# CAC 40 (default preset, bundled in the package), 5 annual values each
uv run lseg-extract goodwill --preset cac40 --years 5
uv run lseg-extract goodwill --preset cac40 --years 5 --output goodwill_cac40.csv

# Exhaustive: all French listed companies incl. delisted, 1995-2025
uv run lseg-extract goodwill --preset all-france --start-year 1995 --end-year 2025 \
  --output goodwill_france_1995_2025.csv

# Custom universe, fields, or pacing for big extracts
uv run lseg-extract goodwill --universe @my_rics.txt --years 10 --batch-size 50
uv run lseg-extract goodwill --universe "SCREEN(...)" --years 5
```

```python
from lseg_extractor.goodwill import get_goodwill_history
from lseg_extractor.session import session_scope

with session_scope():
    df = get_goodwill_history("cac40", years=5)  # or "all-france" / ["TTE.PA", ...] / "@file.txt"
```

## ESG measures (Asset4-based, lseg-data native module)

Equivalent of Datastream-for-Office ESG grids (see `docs/esg-fields.md` for the
mapping): per-company measures snapshot, or fiscal-year ranged.

```bash
uv run lseg-extract esg --preset cac40
uv run lseg-extract esg --preset cac40 --start 2020 --end 2024 --output esg_cac40.csv
uv run lseg-extract esg --universe "TTE.PA,MC.PA,SAN.PA" --output esg.csv
```

```python
from lseg_extractor.client import get_esg_measures
from lseg_extractor.session import session_scope

with session_scope():
    df = get_esg_measures(["TTE.PA", "MC.PA"], start=2020, end=2024)
```

## Reuse from Python / REST API / frontend backend

`client.py` is import-safe (no prints, no file I/O, no Typer) — it returns
`pandas.DataFrame`:

```python
from dotenv import load_dotenv
load_dotenv()
from lseg_extractor.client import get_snapshot
from lseg_extractor.session import session_scope

with session_scope():  # resolves desktop vs LDPv2 from env
    df = get_snapshot(["IBM.N", "VOD.L"], ["BID", "ASK"])
print(df.head())

# Or inject settings explicitly (e.g. per-request creds in a REST handler):
from lseg_extractor.config import Settings
with session_scope(Settings(LSEG_SESSION="platform-ldpv2", ...)):
    ...
```

See `examples/quickstart.py`.

## Project layout

| Path | Purpose |
|---|---|
| `pyproject.toml` | uv project, `lseg-data>=2,<3`, pandas, pyarrow, typer, dotenv, pydantic-settings; `lseg-extract` script |
| `lseg-data.config.json` | Committed placeholder template (no secrets) |
| `.env.example` | Documented env vars |
| `src/lseg_extractor/config.py` | Env-first `Settings` (session choice, creds) |
| `src/lseg_extractor/session.py` | Dual-auth factory + `session_scope()` context manager |
| `src/lseg_extractor/client.py` | `get_snapshot`, `get_history`, `get_fundamentals`, `get_news_headlines`, `search_instruments` → DataFrame |
| `src/lseg_extractor/cli.py` | Thin Typer shell (arg parsing + file output only) |
| `tests/` | Mocked tests, no network/credentials needed |

## Quality gates

```bash
uv run --group dev pytest -q
uv run --group dev ruff check src tests
uv run --group dev ruff format --check src tests
uv run lseg-extract --help
```

## Notes & limits (v1)

- Content coverage: snapshot, history, fundamentals/reference, news, search.
  Streaming (Delivery layer `omm_stream`), bulk files, and IPA analytics are
  deferred to phase 2.
- Deployed ADS connections are not implemented in v1 (real-time only, no
  history/news) — extension point left in `session.py`.
- `lseg-data` is pinned `>=2,<3` (v1 `refinitiv-data` → v2 `lseg-data` rename).
- Never commit `.env` or real AppKeys — the JSON stays a template.
