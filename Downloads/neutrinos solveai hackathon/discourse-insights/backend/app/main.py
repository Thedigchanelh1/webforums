import logging

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import database as db
from app.config import get_settings
from app.discourse_client import DiscourseAPIError, DiscourseClient
from app.models import (
    DashboardStats, DiscourseCategory, DiscourseSettings, DiscourseSettingsUpdate,
    Issue, ProviderInfo, ScrapedPost, ScrapeRequest, ScrapeRunResult,
)
from app.llm_providers import PROVIDER_CATALOG, get_provider_info, LLMError
from app.pipeline import run_full_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

settings = get_settings()
app = FastAPI(title="Forum Insights API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# in-memory flag so the frontend can show "a run is already in progress"
_run_state = {"running": False}


@app.on_event("startup")
async def on_startup():
    await db.init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/providers", response_model=list[ProviderInfo])
async def list_providers():
    return PROVIDER_CATALOG


async def _resolve_discourse_config(overrides: dict | None = None) -> dict:
    """Precedence, highest wins: an explicit one-off override passed with a
    scan request > what's saved server-side in the database (set via the
    Discourse Settings panel, no rebuild needed) > backend/.env (only ever
    used as the very first boot default, before anyone has saved anything).
    """
    overrides = overrides or {}
    persisted = await db.get_discourse_settings()

    def pick(override_val, db_key, env_val):
        if override_val not in (None, ""):
            return override_val
        if persisted.get(db_key):
            return persisted[db_key]
        return env_val

    category_raw = pick(overrides.get("discourse_category_id"), "discourse_category_id", settings.discourse_category_id)
    max_pages_raw = pick(overrides.get("max_pages"), "discourse_max_pages", settings.discourse_max_pages)

    return {
        "discourse_base_url": pick(overrides.get("discourse_base_url"), "discourse_base_url", settings.discourse_base_url),
        "discourse_api_key": pick(overrides.get("discourse_api_key"), "discourse_api_key", settings.discourse_api_key),
        "discourse_api_username": pick(overrides.get("discourse_api_username"), "discourse_api_username", settings.discourse_api_username),
        "discourse_category_id": int(category_raw) if category_raw not in (None, "") else None,
        "max_pages": int(max_pages_raw) if max_pages_raw not in (None, "") else settings.discourse_max_pages,
    }


@app.get("/api/discourse-settings", response_model=DiscourseSettings)
async def get_discourse_settings():
    # Reflects whatever a scan would ACTUALLY use right now: a saved,
    # persisted override if one exists, otherwise the backend/.env default.
    # The API key itself is never returned — only whether one is configured.
    resolved = await _resolve_discourse_config()
    return DiscourseSettings(
        discourse_base_url=resolved["discourse_base_url"],
        max_pages=resolved["max_pages"],
        api_key_configured=bool(resolved["discourse_api_key"]),
        discourse_category_id=resolved["discourse_category_id"],
    )


@app.post("/api/discourse-settings", response_model=DiscourseSettings)
async def save_discourse_settings_endpoint(payload: DiscourseSettingsUpdate):
    # This is what makes "paste a new URL/key and go" actually work: it
    # writes straight into the SQLite database (survives restarts, no Docker
    # rebuild involved) rather than only living in this request or a
    # browser's localStorage. Only fields the user actually filled in are
    # touched — leaving the API key field blank keeps whatever was saved
    # before, it does NOT erase it.
    if payload.discourse_base_url is not None:
        if not payload.discourse_base_url.strip():
            raise HTTPException(status_code=400, detail="Discourse base URL cannot be empty.")
        if not payload.discourse_base_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Discourse base URL must start with http:// or https://")

    await db.save_discourse_settings({
        "discourse_base_url": payload.discourse_base_url.strip().rstrip("/") if payload.discourse_base_url else None,
        "discourse_api_key": payload.discourse_api_key.strip() if payload.discourse_api_key else None,
        "discourse_api_username": payload.discourse_api_username.strip() if payload.discourse_api_username else None,
        "discourse_category_id": payload.discourse_category_id if payload.discourse_category_id is not None else None,
        "discourse_max_pages": payload.max_pages if payload.max_pages is not None else None,
    })
    return await get_discourse_settings()


@app.get("/api/discourse-categories", response_model=list[DiscourseCategory])
async def get_discourse_categories(base_url: str | None = None, api_key: str | None = None, api_username: str | None = None):
    # Lets the settings panel populate a category dropdown by calling the
    # real Discourse API (GET /categories.json) rather than guessing ids.
    # Falls back to the currently resolved (persisted or .env) target when
    # the caller doesn't pass an explicit base_url — e.g. right after saving.
    try:
        resolved = await _resolve_discourse_config({
            "discourse_base_url": base_url,
            "discourse_api_key": api_key,
            "discourse_api_username": api_username,
        })
        client = DiscourseClient(
            base_url=resolved["discourse_base_url"],
            api_key=resolved["discourse_api_key"],
            api_username=resolved["discourse_api_username"],
        )
        cats = await client.list_categories()
        return [DiscourseCategory(**c) for c in cats]
    except DiscourseAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Could not reach Discourse API: {e}")


@app.post("/api/scrape", response_model=ScrapeRunResult)
async def trigger_scrape(payload: ScrapeRequest, background_tasks: BackgroundTasks):
    if _run_state["running"]:
        raise HTTPException(status_code=409, detail="A scrape run is already in progress.")

    try:
        info = get_provider_info(payload.ai_provider)
    except LLMError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if info["requires_api_key"] and not payload.api_key.strip():
        raise HTTPException(status_code=400, detail=f"{info['label']} requires an API key.")

    resolved = await _resolve_discourse_config({
        "discourse_base_url": payload.discourse_base_url,
        "discourse_api_key": payload.discourse_api_key,
        "discourse_api_username": payload.discourse_api_username,
        "discourse_category_id": payload.discourse_category_id,
        "max_pages": payload.max_pages,
    })

    async def _run():
        _run_state["running"] = True
        try:
            await run_full_pipeline(
                provider=payload.ai_provider,
                api_key=payload.api_key,
                model=payload.model,
                llm_base_url=payload.llm_base_url,
                fetch_full_content=payload.fetch_full_content,
                discourse_base_url=resolved["discourse_base_url"],
                discourse_api_key=resolved["discourse_api_key"],
                discourse_api_username=resolved["discourse_api_username"],
                discourse_category_id=resolved["discourse_category_id"],
                max_pages=resolved["max_pages"],
            )
        finally:
            _run_state["running"] = False

    background_tasks.add_task(_run)
    return ScrapeRunResult(run_id=0, posts_scraped=0, issues_found=0, status="started")


@app.get("/api/scrape/status")
async def scrape_status():
    return {"running": _run_state["running"]}


@app.get("/api/scrape/last")
async def last_run_status():
    run = await db.get_latest_run()
    if not run:
        return {"status": "none"}
    return {
        "status": run["status"],
        "error": run["error"],
        "posts_scraped": run["posts_scraped"],
        "issues_found": run["issues_found"],
        "finished_at": run["finished_at"],
    }


@app.get("/api/stats", response_model=DashboardStats)
async def get_stats():
    stats = await db.get_dashboard_stats()
    return DashboardStats(**stats)


@app.get("/api/issues", response_model=list[Issue])
async def get_issues():
    issues = await db.get_latest_issues()
    return [
        Issue(
            id=i["id"], title=i["title"], summary=i["summary"], urgency=i["urgency"],
            urgency_reason=i["urgency_reason"], frequency=i["frequency"],
            post_ids=i["post_ids"], sample_languages=i["sample_languages"],
        )
        for i in issues
    ]


@app.get("/api/issues/{issue_id}/posts", response_model=list[ScrapedPost])
async def get_issue_posts(issue_id: int):
    issues = await db.get_latest_issues()
    match = next((i for i in issues if i["id"] == issue_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Issue not found")
    posts = await db.get_posts_by_ids(match["post_ids"])
    return [ScrapedPost(**p) for p in posts]


@app.get("/api/posts", response_model=list[ScrapedPost])
async def list_posts():
    posts = await db.get_all_posts()
    return [ScrapedPost(**p) for p in posts]
