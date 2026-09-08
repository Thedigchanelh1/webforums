"""
Discourse REST API client.

This replaces the old HTML/CSS scraper entirely. Discourse ships a first-class,
authenticated JSON API — there is nothing to "scrape" here: we call documented
endpoints with an API key and get back structured data directly.

Auth: every request carries `Api-Key` + `Api-Username` headers. Generate a key
at {your-forum}/admin/api/keys — scope it to "Global" (read) or, better, a
scoped key limited to `topics#latest`, `topics#show`, `categories#index`, and
`search#query` for least privilege.

Endpoints used:
  GET /categories.json                         → category list (for filtering + display)
  GET /latest.json?page=N                       → paginated "latest topics" feed
  GET /c/{slug}/{category_id}.json?page=N       → paginated topics within one category
  GET /t/{topic_id}.json                        → full topic, including every post's
                                                   raw/cooked HTML body (used when
                                                   fetch_full_content=True)
  GET /search.json?q=...                        → keyword search across the forum
                                                   (used for the optional keyword filter)

Rate limiting: Discourse enforces per-key rate limits server-side (headers
`X-RateLimit-Remaining` / `Retry-After` on a 429). We respect `Retry-After`
on 429s and otherwise self-throttle with a small delay between requests so a
scan behaves as a good API citizen rather than hammering the instance.
"""
import asyncio
import logging

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings

logger = logging.getLogger("discourse_client")


class DiscourseAPIError(Exception):
    pass


class DiscourseClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        api_username: str | None = None,
        max_pages: int | None = None,
        category_id: int | None = None,
    ):
        s = get_settings()
        self.base_url = (base_url or s.discourse_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else s.discourse_api_key
        self.api_username = api_username if api_username is not None else s.discourse_api_username
        self.max_pages = max_pages if max_pages is not None else s.discourse_max_pages
        self.category_id = category_id if category_id is not None else (s.discourse_category_id or None)
        self.request_delay = s.discourse_request_delay_ms / 1000
        self.timeout = s.discourse_timeout_ms / 1000
        self._semaphore = asyncio.Semaphore(s.discourse_max_concurrency)

    def _headers(self) -> dict:
        # Discourse accepts an unauthenticated request too (public forums serve
        # latest.json without a key) but auth raises rate limits substantially
        # and is required for private categories.
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Api-Key"] = self.api_key
            headers["Api-Username"] = self.api_username or "system"
        return headers

    def _strip_html(self, html: str) -> str:
        """Turns Discourse's rendered post HTML into clean plain text for the
        LLM — this is the actual 'input quality' lever, not just an HTML
        formatting detail. A naive .get_text() flattens EVERYTHING into
        plain text: someone else's earlier post duplicated verbatim inside
        a quote block, a 40-line stack trace, a link-preview card's scraped
        metadata — all of it looks identical to the person's actual words
        once flattened. At small scale that's just noise; at scale (more
        batches, tighter effective context per batch) it's tokens spent on
        duplicate/irrelevant content instead of the signal that actually
        drives clustering and urgency scoring. So we strip the known-noisy
        elements first and only flatten what's left.
        """
        soup = BeautifulSoup(html or "", "lxml")

        # Quoted replies (Discourse renders these as <aside class="quote">
        # or plain <blockquote>) repeat another post's text verbatim inside
        # this one — duplicate signal, not new information.
        for quote in soup.select("aside.quote, blockquote"):
            quote.decompose()

        # Code blocks / stack traces add length without adding anything
        # useful for clustering "what problem is this" — a short marker
        # preserves the fact that code was shared without burning the
        # token budget on its contents.
        for code in soup.select("pre, code"):
            code.replace_with(" [code snippet omitted] ")

        # Onebox link previews (Discourse auto-expands URLs into rich
        # cards) inject the target page's own title/description text,
        # which isn't the poster's words at all.
        for onebox in soup.select("aside.onebox"):
            onebox.decompose()

        text = soup.get_text(" ", strip=True)
        # Collapse any run of whitespace left behind by the removals above
        # into single spaces — cheap, and keeps token counts honest.
        return " ".join(text.split())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    )
    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = await client.get(url, params=params, timeout=self.timeout)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "5"))
            logger.warning("Discourse rate limit hit on %s — waiting %.1fs", url, retry_after)
            await asyncio.sleep(retry_after)
            resp = await client.get(url, params=params, timeout=self.timeout)
        if resp.status_code == 403:
            raise DiscourseAPIError(
                f"403 from {url} — check the API key's scope/username, or whether this "
                f"category requires authentication."
            )
        resp.raise_for_status()
        return resp.json()

    async def list_categories(self) -> list[dict]:
        async with httpx.AsyncClient(headers=self._headers()) as client:
            data = await self._get(client, "/categories.json")
        cats = data.get("category_list", {}).get("categories", [])
        return [{"id": c["id"], "name": c["name"], "slug": c["slug"], "topic_count": c.get("topic_count", 0)} for c in cats]

    def _topic_list_path(self, page: int) -> tuple[str, dict]:
        if self.category_id:
            return f"/c/{self.category_id}.json", {"page": page}
        return "/latest.json", {"page": page}

    async def _fetch_full_topic(self, client: httpx.AsyncClient, topic_id: int) -> str | None:
        async with self._semaphore:
            try:
                data = await self._get(client, f"/t/{topic_id}.json")
                posts = data.get("post_stream", {}).get("posts", [])
                if posts:
                    return self._strip_html(posts[0].get("cooked", ""))
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not fetch full content for topic %s: %s", topic_id, e)
            finally:
                await asyncio.sleep(self.request_delay)
        return None

    async def fetch_topics(self, fetch_full_content: bool = False) -> list[dict]:
        """Pull topics via the Discourse JSON API and normalise them into the
        same post shape the rest of the pipeline (analyzer/db) expects."""
        headers = self._headers()
        all_topics: dict[str, dict] = {}

        async with httpx.AsyncClient(headers=headers) as client:
            page = 0
            while page < self.max_pages:
                path, params = self._topic_list_path(page)
                logger.info("Fetching Discourse topic list page %d: %s%s", page, self.base_url, path)
                try:
                    data = await self._get(client, path, params=params)
                except Exception as e:  # noqa: BLE001
                    if page == 0:
                        # A failure on the very first request means something
                        # is actually wrong (network, blocked, bad URL, wrong
                        # category id) — not "we've reached the end of the
                        # forum's topics." Raising here is what lets a scan
                        # be correctly marked "failed" with a real error
                        # message, instead of silently finishing as a
                        # "completed" scan with zero results and no
                        # explanation, which is what happened before this fix.
                        raise DiscourseAPIError(
                            f"Could not fetch topics from {self.base_url}{path}: {e}"
                        ) from e
                    logger.error(
                        "Failed to fetch %s after retries: %s — stopping pagination, keeping %d topics already collected",
                        path, e, len(all_topics),
                    )
                    break

                topics = data.get("topic_list", {}).get("topics", [])
                if not topics:
                    logger.info("No topics on page %d — stopping pagination.", page)
                    break

                for topic in topics:
                    topic_id = topic["id"]
                    slug = topic.get("slug", "")
                    topic_url = f"{self.base_url}/t/{slug}/{topic_id}"
                    all_topics[topic_url] = {
                        "_topic_id": topic_id,
                        "title": topic.get("title", ""),
                        # excerpt is Discourse's own truncated preview; replaced with
                        # the real first-post body below when fetch_full_content=True.
                        "content": self._strip_html(topic.get("excerpt", "")) or topic.get("title", ""),
                        "author": (
                            topic.get("last_poster_username")
                            or (topic.get("posters", [{}])[0].get("user_id") if topic.get("posters") else "unknown")
                            or "unknown"
                        ),
                        "timestamp": topic.get("created_at", ""),
                        "reply_count": topic.get("reply_count", max(topic.get("posts_count", 1) - 1, 0)),
                        "url": topic_url,
                    }

                if not data.get("topic_list", {}).get("more_topics_url"):
                    break
                page += 1
                await asyncio.sleep(self.request_delay)

            if fetch_full_content:
                tasks = [self._fetch_full_topic(client, t["_topic_id"]) for t in all_topics.values()]
                full_contents = await asyncio.gather(*tasks)
                for topic, full_content in zip(all_topics.values(), full_contents):
                    if full_content:
                        topic["content"] = full_content

        for topic in all_topics.values():
            topic.pop("_topic_id", None)

        logger.info("Discourse API fetch complete: %d unique topics collected", len(all_topics))
        return list(all_topics.values())
