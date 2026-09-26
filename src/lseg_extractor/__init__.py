"""lseg_extractor — reusable primitives + thin CLI for the LSEG Data Platform."""

from lseg_extractor.client import (
    get_fundamentals,
    get_history,
    get_news_headlines,
    get_snapshot,
    search_instruments,
)
from lseg_extractor.config import Settings, get_settings
from lseg_extractor.goodwill import (
    FRENCH_PRESETS,
    GOODWILL_FIELD,
    get_goodwill_history,
    load_french_universe,
    to_tidy_goodwill,
)
from lseg_extractor.session import close_session, open_lseg_session, session_scope

__all__ = [
    "FRENCH_PRESETS",
    "GOODWILL_FIELD",
    "Settings",
    "close_session",
    "get_fundamentals",
    "get_goodwill_history",
    "get_history",
    "get_news_headlines",
    "get_settings",
    "get_snapshot",
    "load_french_universe",
    "open_lseg_session",
    "search_instruments",
    "session_scope",
    "to_tidy_goodwill",
]
