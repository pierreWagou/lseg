"""Goodwill history for French listed companies (needs Workspace session)."""

from dotenv import load_dotenv

load_dotenv()

from lseg_extractor.goodwill import get_goodwill_history
from lseg_extractor.session import session_scope

with session_scope():
    df = get_goodwill_history("all-france", years=35, start_year=1995, end_year=2025)
print(df.head(10).to_string())
print(f"\n{df['ric'].nunique()} companies × {df['fiscal_year'].nunique()} years")
df.to_csv("goodwill_france_1995_2025.csv", index=False)
print("Wrote goodwill_france_1995_2025.csv")
