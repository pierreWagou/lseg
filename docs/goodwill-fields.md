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
#   "Curn": "EUR"}` — note `SDate`/`EDate` are **integer offsets**
#   (0 = today, -N = N years back), not date strings.
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
# ## Probe commands
#
# ```bash
# uv run lseg-extract goodwill --preset cac40 --years 5          # fast check
# uv run lseg-extract goodwill --preset all-france \
#   --start-year 1995 --end-year 2025 --output goodwill_france_1995_2025.csv
# ```
