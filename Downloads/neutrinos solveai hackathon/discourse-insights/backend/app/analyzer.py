"""
LLM-driven analysis pipeline.

Takes raw scraped posts (in any language) and asks the configured LLM to:
  1. Cluster them into unified issue categories (translation-aware —
     posts about the same problem in different languages get merged).
  2. Write one concise, English summary per issue.
  3. Assign an urgency (High / Medium / Low) based on sentiment, impact
     severity, and frustration-language cues.
  4. Report frequency = how many posts belong to that issue.

Provider-agnostic: works with whichever provider/model/key the user picked
in the settings panel (Anthropic, OpenAI, Groq, DeepSeek, or a local
Ollama instance) via app.llm_providers.get_client().

Posts are batched (BATCH_SIZE) to stay well within context limits and to
keep individual requests fast; batch results are then merged by a final
consolidation pass so near-duplicate issues across batches collapse into
one entry.
"""
import concurrent.futures
import json
import logging

from app.llm_providers import LLMError, get_client, parse_json_response

logger = logging.getLogger("analyzer")

BATCH_SIZE = 40
# How many batch/consolidation LLM calls run at once. This is the single
# biggest scale fix: previously every batch ran one after another in a
# for-loop, so scan time grew linearly with post count. Running several
# concurrently (via a thread pool — the provider SDKs are synchronous, but
# each call is I/O-bound waiting on the network, so threads parallelize
# this fine) cuts wall-clock time roughly proportionally to this number,
# without changing anything about correctness.
MAX_CONCURRENT_LLM_CALLS = 5

SYSTEM_PROMPT = """You are an analyst for a company's user support forum. You will be given \
a batch of forum posts (title, content, reply_count, id) which may be written in several \
different languages. Your job:

1. Group posts describing the SAME underlying issue into one cluster, even if they are \
   written in different languages or phrased very differently.
2. For each cluster, write a short, clear ISSUE TITLE and a 1-3 sentence SUMMARY, both in \
   English, regardless of the original post language(s).
3. Assign an URGENCY of "High", "Medium", or "Low":
   - High: data loss, security issue, payment/billing failure, total feature outage, or posts \
     with strong frustration/anger language ("unacceptable", "losing money", "urgent", "broken \
     for days").
   - Medium: a feature working incorrectly or a significant inconvenience, but a workaround \
     exists or impact is partial.
   - Low: minor UI issues, cosmetic bugs, feature requests, or general questions.
4. Give a one-sentence URGENCY_REASON explaining the call.
5. List the post ids belonging to each cluster.
6. Note which languages appeared in that cluster's posts (ISO 639-1 codes, e.g. "en", "es", "hi").

Respond ONLY with a JSON array (no prose, no markdown fences), where each element is:
{
  "title": string,
  "summary": string,
  "urgency": "High" | "Medium" | "Low",
  "urgency_reason": string,
  "post_ids": [int, ...],
  "languages": [string, ...]
}

Every post id given to you must appear in exactly one cluster. If a post is a one-off with no \
related posts, it still becomes its own single-post cluster."""

CONSOLIDATE_SYSTEM_PROMPT = """You are merging issue lists produced independently from several \
batches of the same forum. Several entries may describe the same underlying issue — merge those, \
summing their post_ids and taking the highest urgency among them. Keep unrelated issues separate. \
Respond ONLY with a JSON array in the same shape you were given: \
[{"title":str,"summary":str,"urgency":"High"|"Medium"|"Low","urgency_reason":str,"post_ids":[int],"languages":[str]}]"""


class Analyzer:
    def __init__(self, provider: str, api_key: str, model: str, base_url: str | None = None):
        self.client = get_client(provider, api_key, model, base_url)

    def _call_llm(self, system: str, user_content: str) -> list[dict]:
        try:
            text = self.client.complete(system, user_content)
        except LLMError as e:
            logger.error(str(e))
            raise
        return parse_json_response(text)

    def _call_llm_with_retry(self, system: str, user_content: str, label: str) -> list[dict]:
        """Wraps _call_llm with one retry on malformed/empty JSON. Previously
        a single garbled response silently dropped that batch's issues with
        no warning; at scale (more batches = more chances of a truncated or
        malformed response) that quietly lost real data. One retry catches
        the common transient case; a second failure is logged clearly rather
        than swallowed."""
        for attempt in (1, 2):
            result = self._call_llm(system, user_content)
            if result:
                return result
            logger.warning("%s: empty/malformed JSON response (attempt %d/2)%s", label, attempt, " — retrying" if attempt == 1 else "")
        logger.error("%s: still malformed after retry — its issues are missing from this run.", label)
        return []

    def _batch_to_prompt(self, posts: list[dict]) -> str:
        slim = [
            {
                "id": p["id"],
                "title": p["title"],
                "content": (p["content"] or "")[:800],
                "reply_count": p.get("reply_count", 0),
            }
            for p in posts
        ]
        return json.dumps(slim, ensure_ascii=False)

    def _consolidate_pair(self, list_a: list[dict], list_b: list[dict]) -> list[dict]:
        if not list_a:
            return list_b
        if not list_b:
            return list_a
        combined = list_a + list_b
        merged = self._call_llm_with_retry(
            CONSOLIDATE_SYSTEM_PROMPT, json.dumps(combined, ensure_ascii=False), "consolidation pair"
        )
        # If even the retry came back malformed, fall back to the unmerged
        # combined list rather than losing those issues entirely — you get
        # a few duplicate-looking entries instead of silently missing ones.
        return merged or combined

    def _consolidate_hierarchically(self, issue_lists: list[list[dict]]) -> list[dict]:
        """Merges N batches' worth of issue-lists in stages instead of one
        flat pass over everything at once. A single final merge call asked
        to deduplicate across dozens of batches at once was the second big
        scale problem: past a handful of batches it started missing
        duplicate issues, since it's comparing far more items than a single
        call reliably handles. Merging in pairs, round by round, means each
        individual merge call only ever has to compare two lists — so
        accuracy doesn't degrade as total post count grows, it just takes
        one more round (log2(batches) rounds total)."""
        lists = issue_lists
        round_num = 1
        while len(lists) > 1:
            pairs = [(lists[i], lists[i + 1]) for i in range(0, len(lists) - 1, 2)]
            leftover = lists[-1] if len(lists) % 2 else None
            logger.info("Consolidation round %d: merging %d pairs (%d issue-lists total)", round_num, len(pairs), len(lists))
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_LLM_CALLS, max(len(pairs), 1))) as pool:
                merged = list(pool.map(lambda pair: self._consolidate_pair(*pair), pairs))
            if leftover is not None:
                merged.append(leftover)
            lists = merged
            round_num += 1
        return lists[0] if lists else []

    def analyze(self, posts: list[dict]) -> list[dict]:
        """posts: list of dicts with at least id, title, content, reply_count."""
        if not posts:
            return []

        batches = [posts[i:i + BATCH_SIZE] for i in range(0, len(posts), BATCH_SIZE)]

        if len(batches) == 1:
            batch_issue_lists = [self._call_llm_with_retry(SYSTEM_PROMPT, self._batch_to_prompt(batches[0]), "batch 1/1")]
        else:
            logger.info("Analyzing %d batches, up to %d concurrently", len(batches), MAX_CONCURRENT_LLM_CALLS)
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_LLM_CALLS, len(batches))) as pool:
                futures = {
                    pool.submit(self._call_llm_with_retry, SYSTEM_PROMPT, self._batch_to_prompt(batch), f"batch {i + 1}/{len(batches)}"): i
                    for i, batch in enumerate(batches)
                }
                results_by_index: dict[int, list[dict]] = {}
                for future in concurrent.futures.as_completed(futures):
                    results_by_index[futures[future]] = future.result()
            batch_issue_lists = [results_by_index[i] for i in range(len(batches))]

        final = batch_issue_lists[0] if len(batch_issue_lists) == 1 else self._consolidate_hierarchically(batch_issue_lists)

        # Defensive normalization: parse_json_response only guarantees valid
        # JSON, not that every required key is actually present. A single
        # issue missing "title" or "urgency" used to crash the whole run
        # with a raw KeyError several layers downstream (in database.py),
        # marking the entire scan "failed" over one malformed entry.
        normalized = []
        for issue in final:
            if not isinstance(issue, dict):
                continue
            issue.setdefault("title", "Untitled issue")
            issue.setdefault("summary", "")
            issue.setdefault("post_ids", [])
            if issue.get("urgency") not in ("High", "Medium", "Low"):
                issue["urgency"] = "Low"
            normalized.append(issue)
        final = normalized

        # Frequency = number of posts backing the issue, weighted lightly by reply_count
        # so heavily-discussed threads rank a bit higher even with the same post count.
        posts_by_id = {p["id"]: p for p in posts}
        for issue in final:
            post_ids = issue.get("post_ids", [])
            reply_weight = sum(posts_by_id.get(pid, {}).get("reply_count", 0) for pid in post_ids)
            issue["frequency"] = len(post_ids) + reply_weight
            issue["sample_languages"] = issue.pop("languages", [])
            issue["urgency_reason"] = issue.get("urgency_reason", "")

        final.sort(key=lambda x: (x["urgency"] != "High", x["urgency"] != "Medium", -x["frequency"]))
        return final
