"""Minimal end-to-end example (needs Workspace open or LDPv2 creds in .env)."""

from dotenv import load_dotenv

load_dotenv()

from lseg_extractor.client import get_snapshot
from lseg_extractor.session import session_scope

with session_scope():
    df = get_snapshot(["IBM.N", "VOD.L"], ["BID", "ASK"])
print(df.head())
