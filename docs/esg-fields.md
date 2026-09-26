# ESG fields (lseg-data native module) — STATUS: UNCONFIRMED live
#
# Colleague's Excel grid is Datastream-for-Office (`DSGRID` over `LAST4ESG`
# with Datastream mnemonics `W06004/W06001/WC07021/W06008/A4STATUS/A4NAME/...`).
# That API family (DSWS) needs separate Datastream credentials, which we don't
# have — so we reproduce *equivalent* data via `lseg.data.content.esg` on the
# existing Workspace session.
#
# ## Module surface (installed lseg-data 2.1.1, verified by introspection)
#
# - `basic_overview.Definition(universe)` — per-company ESG snapshot.
# - `standard_measures.Definition(universe, start=None, end=None)` — measures,
#   optionally for fiscal years `[start, end]`.
# - `standard_scores`, `full_scores`, `full_measures`, `universe` also exist;
#   only the first two are wrapped until live use shows a need.
# - All `get_data(session=None)` → `response.data.df`; closed best-effort.
#
# ## Curated defaults
#
# - CLI `esg` uses `standard_measures` (snapshot when no `--start/--end`).
# - Identity columns (ISIN, name, country) come from the existing snapshot
#   path: `TR.ISINCode`, `TR.CommonName`, `TR.HeadquartersCountry`
#   (see `examples/esg_france.py` for the join pattern).
# - `all-france` screener string is passed through as universe (backend
#   resolves it, same as goodwill); live run must confirm.
#
# ## Best-effort W-code mapping (unverified — Datastream Navigator or colleague
# to confirm; NOT blocking since we define our own measure set)
#
# - `A4STATUS` / `A4NAME` → Asset4 universe coverage/identity ≈ ESG `universe`
#   view + identity fields.
# - `W06004` / `W06001` / `W06008` → likely ESG combined/pillar scores ≈
#   `standard_scores` / `standard_measures` columns (pin exact names live).
# - `WC07021` → Worldscope fundamental item (pin live if needed).
# - `GEOGN` / `IBCTRY` → geography/country ≈ `TR.HeadquartersCountry`.
#
# ## Probe commands (Workspace box)
#
# ```bash
# uv run lseg-extract esg --preset cac40                        # snapshot
# uv run lseg-extract esg --preset cac40 --start 2020 --end 2024 --output esg.csv
# ```
#
# If the probe returns access-denied rather than data, the account lacks ESG
# entitlement → admin ticket, not a code problem.
