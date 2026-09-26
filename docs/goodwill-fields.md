# Goodwill field discovery (Step-0 spike) — STATUS: UNCONFIRMED, needs live session
#
# Web/GitHub search did not confirm the exact `TR.` goodwill data-item name,
# so v1 pins a single constant (`GOODWILL_FIELD` in `src/lseg_extractor/goodwill.py`)
# that is a 1-line change once confirmed.
#
# ## Candidate
#
# - Primary: `TR.Goodwill` (follows the `TR.Revenue` / `TR.GrossProfit` naming pattern
#   used by `fundamental_and_reference`).
# - If `TR.Goodwill` returns `<NA>`/error, confirm via Workspace **Data Item Browser (DIB)**:
#   search "goodwill", balance-sheet section, and update `GOODWILL_FIELD`.
#
# ## History parameters (also unconfirmed live)
#
# `get_goodwill_history` defaults to a single `get_fundamentals` call with:
#
#     {"SDate": "-<years>Y", "EDate": "0D", "Frq": "FY", "Curn": "<currency>"}
#
# (`SDate`/`EDate`/`Frq`/`Curn` are standard DIB parameter keys for `TR.` items;
# `Frq=FY` = annual fiscal periods, `Curn=EUR` = convert to euros.)
#
# ## Probe commands (run with Workspace open or LDPv2 creds in `.env`)
#
# ```bash
# cp .env.example .env   # then fill LSEG_APP_KEY (desktop) or LDPv2 trio
# uv run python - <<'EOF'
# from dotenv import load_dotenv; load_dotenv()
# from lseg_extractor.client import get_fundamentals
# from lseg_extractor.session import session_scope
#
# with session_scope():
#     df = get_fundamentals(
#         ["TTE.PA", "MC.PA", "SAN.PA"],
#         ["TR.Goodwill"],
#         parameters={"SDate": "-5Y", "EDate": "0D", "Frq": "FY", "Curn": "EUR"},
#     )
# print(df.to_string())
# EOF
# ```
#
# If the response is wide (periods as columns), `to_tidy_goodwill` in `goodwill.py`
# melts it to long form — no code change needed, just verify column labels parse
# to fiscal years. If the call errors on parameters, retry with `parameters=None`
# (snapshot) to isolate field-name vs parameter issues, then record findings here.
