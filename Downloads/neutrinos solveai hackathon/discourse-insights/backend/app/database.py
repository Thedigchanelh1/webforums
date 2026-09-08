"""
Lightweight persistence layer using SQLite (via aiosqlite).

Kept intentionally simple (no ORM) so the project has zero external
database dependencies to stand up — just a local file.
"""
import json
import os
from datetime import datetime, timezone

import aiosqlite

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    author TEXT,
    timestamp TEXT,
    reply_count INTEGER DEFAULT 0,
    url TEXT UNIQUE,
    language TEXT,
    scraped_at TEXT
);

CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    urgency TEXT NOT NULL,
    urgency_reason TEXT,
    frequency INTEGER DEFAULT 0,
    post_ids TEXT,        -- JSON array of post ids
    sample_languages TEXT, -- JSON array
    run_id INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    posts_scraped INTEGER DEFAULT 0,
    issues_found INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    error TEXT
);

-- Simple key/value store for runtime-editable configuration (currently just
-- the target Discourse instance). This is what makes "paste a new forum URL
-- and API key, no rebuild needed" actually work: the app checks here first,
-- and only falls back to backend/.env if nothing has been saved yet.
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_db() -> aiosqlite.Connection:
    settings = get_settings()
    os.makedirs(os.path.dirname(settings.database_path) or ".", exist_ok=True)
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    # Without this, a second writer arriving while one connection is mid-write
    # gets an immediate "database is locked" error. This makes it wait up to
    # 5s for the lock instead — cheap insurance against the write-contention
    # issue that shows up once scans start writing posts more concurrently
    # (see the parallelized analyzer in analyzer.py).
    await db.execute("PRAGMA busy_timeout = 5000")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


async def start_run() -> int:
    db = await get_db()
    try:
        cur = await db.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, 'running')", (_now(),)
        )
        await db.commit()
        return cur.lastrowid
    finally:
        await db.close()


async def finish_run(run_id: int, posts_scraped: int, issues_found: int, status: str, error: str = "") -> None:
    db = await get_db()
    try:
        await db.execute(
            """UPDATE runs SET finished_at=?, posts_scraped=?, issues_found=?, status=?, error=?
               WHERE id=?""",
            (_now(), posts_scraped, issues_found, status, error, run_id),
        )
        await db.commit()
    finally:
        await db.close()


async def upsert_posts(posts: list[dict]) -> list[int]:
    """Insert posts, skipping duplicates by URL. Returns the ids of all matching rows."""
    db = await get_db()
    ids = []
    try:
        for p in posts:
            await db.execute(
                """INSERT INTO posts (title, content, author, timestamp, reply_count, url, language, scraped_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(url) DO UPDATE SET
                     reply_count=excluded.reply_count,
                     content=excluded.content""",
                (
                    p["title"], p["content"], p.get("author", "unknown"),
                    p.get("timestamp", ""), p.get("reply_count", 0), p["url"],
                    p.get("language"), _now(),
                ),
            )
            cur = await db.execute("SELECT id FROM posts WHERE url=?", (p["url"],))
            row = await cur.fetchone()
            if row:
                ids.append(row["id"])
        await db.commit()
    finally:
        await db.close()
    return ids


async def get_posts_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    db = await get_db()
    try:
        # Chunked rather than one query with N placeholders: SQLite caps the
        # number of parameters allowed in a single statement (historically
        # 999, though modern builds raise this). A very large scan (the UI
        # allows up to 500 pages) could plausibly exceed that in one go —
        # chunking keeps this correct regardless of the exact limit in
        # whatever SQLite build the container ships.
        CHUNK = 500
        rows_out: list[dict] = []
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            placeholders = ",".join("?" * len(chunk))
            cur = await db.execute(f"SELECT * FROM posts WHERE id IN ({placeholders})", chunk)
            rows = await cur.fetchall()
            rows_out.extend(dict(r) for r in rows)
        return rows_out
    finally:
        await db.close()


async def get_all_posts() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT * FROM posts ORDER BY id DESC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def replace_issues(run_id: int, issues: list[dict]) -> None:
    db = await get_db()
    try:
        for issue in issues:
            await db.execute(
                """INSERT INTO issues (title, summary, urgency, urgency_reason, frequency, post_ids,
                                        sample_languages, run_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    issue["title"], issue["summary"], issue["urgency"], issue.get("urgency_reason", ""),
                    issue.get("frequency", len(issue.get("post_ids", []))),
                    json.dumps(issue.get("post_ids", [])),
                    json.dumps(issue.get("sample_languages", [])),
                    run_id, _now(),
                ),
            )
        await db.commit()
    finally:
        await db.close()


async def get_latest_issues() -> list[dict]:
    db = await get_db()
    try:
        cur = await db.execute("SELECT MAX(id) as latest FROM runs WHERE status='completed'")
        row = await cur.fetchone()
        latest_run = row["latest"] if row else None
        if latest_run is None:
            return []
        cur = await db.execute(
            "SELECT * FROM issues WHERE run_id=? ORDER BY frequency DESC", (latest_run,)
        )
        rows = await cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["post_ids"] = json.loads(d["post_ids"] or "[]")
            d["sample_languages"] = json.loads(d["sample_languages"] or "[]")
            out.append(d)
        return out
    finally:
        await db.close()


async def get_latest_run() -> dict | None:
    db_ = await get_db()
    try:
        cur = await db_.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await db_.close()


async def get_dashboard_stats() -> dict:
    db = await get_db()
    try:
        cur = await db.execute("SELECT COUNT(*) as c FROM posts")
        total_posts = (await cur.fetchone())["c"]

        cur = await db.execute("SELECT MAX(id) as latest FROM runs WHERE status='completed'")
        latest_run = (await cur.fetchone())["latest"]

        critical = 0
        total_issues = 0
        trends = []
        last_run_at = None
        if latest_run is not None:
            cur = await db.execute("SELECT * FROM issues WHERE run_id=?", (latest_run,))
            rows = await cur.fetchall()
            total_issues = len(rows)
            critical = sum(1 for r in rows if r["urgency"] == "High")
            trends = [r["title"] for r in sorted(rows, key=lambda r: r["frequency"], reverse=True)[:5]]

            cur = await db.execute("SELECT finished_at FROM runs WHERE id=?", (latest_run,))
            r = await cur.fetchone()
            last_run_at = r["finished_at"] if r else None

        return {
            "total_posts": total_posts,
            "critical_issues": critical,
            "total_issues": total_issues,
            "common_trends": trends,
            "last_run_at": last_run_at,
        }
    finally:
        await db.close()


# --- Runtime-editable app settings (currently: which Discourse instance to
# scan). Stored server-side in the database so they survive container
# restarts and don't require rebuilding the Docker image or editing .env to
# change. .env is only consulted as a first-boot fallback when nothing has
# been saved here yet. ---

DISCOURSE_SETTINGS_KEYS = (
    "discourse_base_url",
    "discourse_api_key",
    "discourse_api_username",
    "discourse_category_id",
    "discourse_max_pages",
)


async def get_discourse_settings() -> dict:
    """Returns only the keys that have actually been saved. Callers merge
    this over the .env-derived defaults, so a partially-filled save (e.g.
    just the URL) doesn't blank out the rest."""
    db = await get_db()
    try:
        placeholders = ",".join("?" * len(DISCOURSE_SETTINGS_KEYS))
        cur = await db.execute(
            f"SELECT key, value FROM app_settings WHERE key IN ({placeholders})",
            DISCOURSE_SETTINGS_KEYS,
        )
        rows = await cur.fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        await db.close()


async def save_discourse_settings(values: dict) -> None:
    """Upserts whichever of DISCOURSE_SETTINGS_KEYS are present (and not
    None) in `values`. Passing an empty string for a field clears it back
    to the .env default; omitting a key entirely leaves it untouched."""
    db = await get_db()
    try:
        for key in DISCOURSE_SETTINGS_KEYS:
            if key not in values or values[key] is None:
                continue
            await db.execute(
                """INSERT INTO app_settings (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, str(values[key])),
            )
        await db.commit()
    finally:
        await db.close()
