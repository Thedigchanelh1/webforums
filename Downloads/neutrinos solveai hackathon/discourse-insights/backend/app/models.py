from typing import Optional, Literal
from pydantic import BaseModel

Urgency = Literal["High", "Medium", "Low"]


class ScrapedPost(BaseModel):
    id: Optional[int] = None
    title: str
    content: str
    author: str = "unknown"
    timestamp: str = ""
    reply_count: int = 0
    url: str
    language: Optional[str] = None


class Issue(BaseModel):
    id: Optional[int] = None
    title: str
    summary: str
    urgency: Urgency
    urgency_reason: str
    frequency: int
    post_ids: list[int]
    sample_languages: list[str] = []


class DiscourseCategory(BaseModel):
    id: int
    name: str
    slug: str
    topic_count: int = 0


class DiscourseSettings(BaseModel):
    discourse_base_url: str
    max_pages: int
    # Whether a key is configured (persisted save or backend/.env) — the key
    # itself is never sent to the frontend.
    api_key_configured: bool = False
    discourse_category_id: Optional[int] = None


class DiscourseSettingsUpdate(BaseModel):
    """Body for POST /api/discourse-settings. Every field is optional and
    independently updatable: send only what changed. Leaving
    discourse_api_key out (or blank) keeps whatever key was saved before —
    it does not clear it. Send an empty string for other fields to reset
    them back to the backend/.env default."""
    discourse_base_url: Optional[str] = None
    discourse_api_key: Optional[str] = None
    discourse_api_username: Optional[str] = None
    discourse_category_id: Optional[int] = None
    max_pages: Optional[int] = None


class ScrapeRequest(BaseModel):
    ai_provider: str
    api_key: str = ""
    model: str
    llm_base_url: Optional[str] = None
    fetch_full_content: bool = False
    # Optional one-off overrides for this single scan only — the normal flow
    # doesn't need these at all, since the Discourse Settings panel saves
    # the target server-side via POST /api/discourse-settings instead.
    discourse_base_url: Optional[str] = None
    discourse_api_key: Optional[str] = None
    discourse_api_username: Optional[str] = None
    discourse_category_id: Optional[int] = None
    max_pages: Optional[int] = None


class ModelOption(BaseModel):
    id: str
    label: str


class ProviderInfo(BaseModel):
    id: str
    label: str
    requires_api_key: bool
    key_help_url: Optional[str] = None
    base_url_editable: bool = False
    default_base_url: Optional[str] = None
    cost_hint: str = ""
    models: list[ModelOption]
    allow_custom_model: bool = False


class ScrapeRunResult(BaseModel):
    run_id: int
    posts_scraped: int
    issues_found: int
    status: str


class DashboardStats(BaseModel):
    total_posts: int
    critical_issues: int
    total_issues: int
    common_trends: list[str]
    last_run_at: Optional[str] = None
