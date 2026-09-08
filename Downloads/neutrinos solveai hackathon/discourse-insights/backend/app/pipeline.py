import logging

from app import database as db
from app.analyzer import Analyzer
from app.discourse_client import DiscourseClient

logger = logging.getLogger("pipeline")


async def run_full_pipeline(
    provider: str,
    api_key: str,
    model: str,
    llm_base_url: str | None = None,
    fetch_full_content: bool = False,
    discourse_base_url: str | None = None,
    discourse_api_key: str | None = None,
    discourse_api_username: str | None = None,
    discourse_category_id: int | None = None,
    max_pages: int | None = None,
) -> dict:
    run_id = await db.start_run()
    try:
        client = DiscourseClient(
            base_url=discourse_base_url,
            api_key=discourse_api_key,
            api_username=discourse_api_username,
            max_pages=max_pages,
            category_id=discourse_category_id,
        )
        raw_posts = await client.fetch_topics(fetch_full_content=fetch_full_content)
        post_ids = await db.upsert_posts(raw_posts)

        # Re-read from DB so every post has its persisted integer id. Note:
        # get_posts_by_ids([]) correctly returns [] — there is deliberately
        # no "fall back to every post ever stored" branch here. An earlier
        # version had one, which meant a scan that legitimately found zero
        # topics (e.g. an empty category, or a forum with nothing new)
        # would silently re-analyze the *entire* historical post table
        # instead of correctly reporting zero results for that run.
        stored_posts = await db.get_posts_by_ids(post_ids)

        analyzer = Analyzer(provider=provider, api_key=api_key, model=model, base_url=llm_base_url)
        issues = analyzer.analyze(stored_posts)
        await db.replace_issues(run_id, issues)

        await db.finish_run(run_id, len(stored_posts), len(issues), "completed")
        return {"run_id": run_id, "posts_scraped": len(stored_posts), "issues_found": len(issues), "status": "completed"}
    except Exception as e:  # noqa: BLE001
        logger.exception("Pipeline run %s failed", run_id)
        await db.finish_run(run_id, 0, 0, "failed", error=str(e))
        return {"run_id": run_id, "posts_scraped": 0, "issues_found": 0, "status": f"failed: {e}"}
