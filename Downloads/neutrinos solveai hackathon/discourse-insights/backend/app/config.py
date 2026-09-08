"""
Centralised, environment-driven configuration.

Everything a real deployment needs lives here — the target Discourse
instance's URL and its API credentials. There are no CSS selectors to
maintain: the Discourse REST API returns structured JSON directly, so
there's nothing forum-HTML-specific left to configure.
"""
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Target Discourse instance
    discourse_base_url: str = "https://discussions.unity.com"
    # Generate at {base_url}/admin/api/keys — scope it to the minimum needed
    # (topics#latest, topics#show, categories#index, search#query).
    discourse_api_key: str = ""
    discourse_api_username: str = "system"
    # Optional: restrict scans to one category (its numeric id, e.g. from
    # /categories.json). Leave 0/None to pull the site-wide "latest" feed.
    discourse_category_id: int | None = None

    # API client behaviour
    discourse_max_pages: int = 20
    discourse_request_delay_ms: int = 300
    discourse_max_concurrency: int = 4
    discourse_timeout_ms: int = 20000

    # Database
    database_path: str = "./data/forum_insights.db"

    # API
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("discourse_category_id", mode="before")
    @classmethod
    def _blank_env_string_to_none(cls, v):
        # Without this, DISCOURSE_CATEGORY_ID= (blank, exactly what
        # .env.example provides) crashes the app at startup — pydantic
        # tries to parse "" as an int and fails, so the container never
        # even starts. Every "nothing works" symptom (empty model dropdown,
        # NetworkError, stale-looking data) can trace back to this if the
        # backend silently isn't running at all.
        if v == "":
            return None
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
