"""Goodwill history for CAC 40 — 5 annual values per company (needs live session)."""

from dotenv import load_dotenv

load_dotenv()

from lseg_extractor.goodwill import get_goodwill_history
from lseg_extractor.session import session_scope

with session_scope():
    df = get_goodwill_history("cac40", years=5)
print(df.head(10).to_string())
print(f"\n{df['ric'].nunique()} companies × {df['fiscal_period'].nunique()} periods")
df.to_csv("goodwill_cac40.csv", index=False)
print("Wrote goodwill_cac40.csv")
