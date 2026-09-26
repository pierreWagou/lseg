"""ESG measures for CAC 40 + identity fields (needs Workspace session)."""

from dotenv import load_dotenv

load_dotenv()

from lseg_extractor.client import get_esg_measures, get_snapshot
from lseg_extractor.goodwill import load_french_universe
from lseg_extractor.session import session_scope

rics = load_french_universe("cac40")
with session_scope():
    esg = get_esg_measures(rics)
    identity = get_snapshot(rics, ["TR.CommonName", "TR.ISINCode", "TR.HeadquartersCountry"])

print(esg.head(10).to_string())
print(f"\n{len(esg)} ESG rows for {esg.index.nunique() if 'Instrument' not in esg.columns else '...'} companies")
esg.to_csv("esg_cac40.csv", index=True)
identity.to_csv("identity_cac40.csv", index=True)
print("Wrote esg_cac40.csv + identity_cac40.csv")
