"""Environment-first configuration (hybrid with lseg-data.config.json).

Secrets live only in env / `.env`. The committed `lseg-data.config.json`
holds non-secret structure (session default, log config) with placeholders.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SessionChoice = Literal["auto", "desktop", "platform-ldpv2"]


class Settings(BaseSettings):
    """Runtime settings resolved from `LSEG_*` env vars / `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="LSEG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    session: SessionChoice = Field(default="auto", alias="LSEG_SESSION")
    app_key: str | None = Field(default=None, alias="LSEG_APP_KEY")
    client_id: str | None = Field(default=None, alias="LSEG_CLIENT_ID")
    client_secret: str | None = Field(default=None, alias="LSEG_CLIENT_SECRET")
    token_scope: str = Field(default="trapi", alias="LSEG_TOKEN_SCOPE")
    goodwill_preset: str = Field(default="cac40", alias="LSEG_GOODWILL_PRESET")
    goodwill_years: int = Field(default=5, alias="LSEG_GOODWILL_YEARS")
    goodwill_start_year: int | None = Field(default=None, alias="LSEG_GOODWILL_START_YEAR")
    goodwill_end_year: int | None = Field(default=None, alias="LSEG_GOODWILL_END_YEAR")

    @property
    def has_platform_credentials(self) -> bool:
        return bool(self.app_key and self.client_id and self.client_secret)

    def effective_session(self) -> Literal["desktop", "platform-ldpv2"]:
        """Resolve `auto` → concrete session type."""
        if self.session == "desktop":
            return "desktop"
        if self.session == "platform-ldpv2":
            return "platform-ldpv2"
        # auto: prefer headless platform when full credentials exist,
        # otherwise fall back to local Workspace desktop.
        if self.has_platform_credentials:
            return "platform-ldpv2"
        return "desktop"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
