# Goodwill field discovery — STATUS: CONFIRMED (Access layer, Workspace session)
#
# ## Confirmed working pattern
#
# - Layer: **Access layer** `ld.get_data(universe, fields, parameters)`
#   (NOT Content-layer `fundamental_and_reference.Definition` — its field
#   dictionary lacks `TR.Goodwill`, hence the old platform error 218).
# - Fields: `TR.Goodwill` + `TR.F.PeriodEndDate` (fiscal close date) +
#   `TR.F.PeriodEndDate.fperiod` (`FY2024`-style label) + `TR.CommonName`.
# - History params: `{"Period": "FY0", "Frq": "FY", "SDate": 0, "EDate": -N,
#   "Curn": "EUR"}` — integer relative offsets, colleague-proven.
#
# ## Response shaping assumption
#
# Requesting a single `TR.Goodwill` value field means every non-helper column
# in the response IS its series by construction — the loader does not require
# any \"goodwill\" header text (headers vary: years, display titles,
# localized names). `reset_index()` artifacts (e.g. an `index` column) are
# excluded structurally. Strict per-field header matching applies only to
# multi-value-field requests.
#
# ## What the official docs add (LSEG Reference Guide 2.0.0.2 + official examples repo)
#
# - `parameters` is \"single key=value global parameter or dictionary of global
#   parameters\"; response = DataFrame with fields as columns, instruments as
#   row index, `<NA>` where not applicable.
# - **String date forms are doc-attested**, ints are not: official examples use
#   `{'SDate': '0CY', 'Curn': 'CAD'}`, `{'SDate': '2020-01-01', 'EDate':
#   '2020-01-09'}`, `{'SDate': '2024-01-01', 'EDate': '-1AM'}` and field-level
#   `'TR.Close(sdate=0d,edate=-9d,frq=d)'`. Our int defaults (`0`/`-N`) work
#   per the colleague's script; `--sdate/--edate` flags accept either form so
#   both can be tried live without code changes.
# - Content FR `Definition` also takes global `parameters` (3rd positional arg)
#   plus per-field `\"TR.X(SDate:0CY)\"` colon syntax — kept in reserve.
# - **Official caution** (`EX-1.01.01-GetData.ipynb`): `get_data` + SDate/EDate
#   for fundamental time series is \"not recommended… alignment issues… use
#   `get_history()`\". Our `get_history` forwards `fields`, so it is the
#   fallback if yearly rows ever misalign — untested, try live if needed.
# - `Frq`/`FY0`/`.fperiod` appear in **no** official example — Eikon/TR-formula
#   knowledge only. DIB remains the authority for item/parameter names.
# - `SCREEN()` as universe is undocumented library-side (`universe` is just
#   \"str or list\"; the TR backend resolves it). Works per colleague; RIC-list
#   presets stay as fallback.
# - Drift note: installed 2.1.1 uses `header_type` where the 2.0.0.2 docs show
#   `use_field_names_in_headers`. Cosmetic; our column matching is
#   case-insensitive.
#
# ## Universe
#
# Exhaustive French scope via screener (active or inactive listed companies,
# HQ in France, euro-converted):
#
#     SCREEN(U(IN(Equity(active or inactive,public,primary))),
#            IN(TR.HQCountryCode,"FR"), CURN=EUR)
#
# Available in code as `FRENCH_SCREENER` / `--preset all-france`.
# `cac40.txt` / `sbf120.txt` presets remain for fast smoke tests.
#
# ## Probe commands (Workspace box)
#
# ```bash
# uv run lseg-extract goodwill --preset cac40 --years 5          # fast check
# # string-form dates instead of int offsets:
# uv run lseg-extract goodwill --preset cac40 --years 5 --sdate 0CY --edate -5Y
# uv run lseg-extract goodwill --preset all-france \
#   --start-year 1995 --end-year 2025 --output goodwill_france_1995_2025.csv
# ```
