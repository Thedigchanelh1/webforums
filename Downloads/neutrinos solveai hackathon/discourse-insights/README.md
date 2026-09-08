# Discourse Insights

A full-stack app that pulls topics from your Discourse community **via
Discourse's official REST API** (no HTML scraping, no CSS selectors, no
headless browser), uses Claude (or another LLM) to cluster them into unified
issues across languages, scores each issue's urgency, and shows it all in a
ranked, dark-mode dashboard.

```
discourse-insights/
├── backend/         FastAPI app: Discourse API client + Claude analysis pipeline + SQLite
│   └── app/
│       ├── config.py            ← Discourse base URL + API credentials live here
│       ├── discourse_client.py   Authenticated Discourse REST API client (categories,
│       │                         latest topics, full topic content, rate-limit handling)
│       ├── analyzer.py           Claude-based clustering / summarizing / urgency scoring
│       ├── pipeline.py           orchestrates fetch → analyze → persist
│       ├── database.py           SQLite persistence (zero external DB needed)
│       └── main.py               API routes
└── frontend/        React + Vite + Tailwind dark-mode dashboard
    └── src/
        ├── components/     MetricCard, IssueTable, UrgencyBadge, IssueDrawer, Header,
        │                    DiscourseSettingsPanel
        └── i18n/            en / es / fr / hi translations (add more freely)
```

## Why the API instead of scraping

Discourse ships a stable, documented JSON API alongside its normal pages.
That means:
- **No CSS selectors to maintain.** A theme update on the forum can no
  longer break data collection.
- **No headless browser.** The old version needed Playwright + Chromium to
  render JS-heavy pages; this version makes plain HTTPS calls, so the
  backend image is a fraction of the size and starts instantly.
- **Authenticated access.** With an API key you can read private categories
  (if the key's user has access) and get much higher rate limits than an
  anonymous scraper would.
- **Structured data from the source.** Titles, authors, timestamps, reply
  counts, and full post bodies (`cooked` HTML, stripped to plain text) come
  back as JSON — nothing is inferred from markup.

## 1. Get a Discourse API key

1. As an admin, go to `{your-forum}/admin/api/keys` → **New API Key**.
2. Scope it to the minimum needed: `topics#latest`, `topics#show`,
   `categories#index`, and (if you plan to extend the search feature)
   `search#query`. Avoid a "Global" all-access key unless you need one.
3. Copy the key — Discourse only shows it once.

If your target community is fully public and you just want a quick test,
you can also leave the key blank; `/latest.json` still works
unauthenticated, just at Discourse's stricter anonymous rate limit.

## 2. AI provider settings live in the UI

There's no `.env` key to set for this part. The dashboard has an **AI
Processor Settings** panel (gear icon in the header) where you pick which
AI service does the analysis:

| Processor | API key needed? | Notes |
|---|---|---|
| **Anthropic Claude** | Yes | Haiku 4.5 (fast/cheap), Sonnet 5 (balanced), Opus 5 (best) |
| **OpenAI (ChatGPT)** | Yes | GPT-5 Mini (fast/cheap), GPT-4o (balanced), GPT-5.5 (best) |
| **Google Gemini** | Yes | Gemini 3.1 Flash-Lite (fast/cheap), Gemini 3.5 Flash (balanced), Gemini 3.5 Pro (best) |
| **Groq** | Yes | Llama 3.1 8B, Llama 3.3 70B, GPT-OSS 120B, Kimi K2 — very fast inference, generous free tier |
| **DeepSeek** | Yes | DeepSeek Chat, DeepSeek Reasoner (both V3.2) — usually the cheapest per scan |
| **Ollama (local, free)** | No | Runs entirely on your own machine — see the networking note below |

Steps:
1. Click the gear icon → pick a processor from the dropdown.
2. Paste your API key (or set a Base URL for Ollama) and pick a model.
3. Click **Save configuration**.

The key/URL you enter is stored only in that browser's `localStorage` and
sent directly to your own backend with each scan request — never written
to the server's disk or database.

### Using Ollama with Docker

If you're running the backend via `docker compose` but Ollama itself on
your host machine, `localhost` inside the backend container does **not**
point at your host:
- **Docker Desktop (Mac/Windows):** `http://host.docker.internal:11434/v1`
- **Linux:** add `network_mode: host` to the `backend` service in
  `docker-compose.yml`, or use your host's LAN IP.

## 3. Discourse settings — set once, no rebuild ever needed

The globe icon opens **Discourse API settings**: base URL, API key, API
username, an optional category filter (populated live from
`GET /categories.json`), and max pages per scan.

Unlike the AI settings, **these are saved server-side** — `POST
/api/discourse-settings` writes them straight into the backend's SQLite
database. That means:
- Changing the target forum or key takes effect on the **next scan**,
  immediately — no `docker compose up --build`, no editing `.env`, no
  restart.
- It survives container restarts, as long as the database volume persists
  (`docker compose down` keeps it; `docker compose down -v` wipes it).
- Leaving the API key field blank when saving **keeps the previously saved
  key** — it never gets silently cleared.
- The dashboard always shows a small **"Source: ..."** pill under the
  header so you can see at a glance exactly which forum the next scan will
  hit. Click it any time to change it.

`backend/.env`'s `DISCOURSE_*` values are only ever used as the **first-boot
default**, before anyone has saved anything through the settings panel. Once
you've saved via the UI once, `.env` is effectively ignored for this — you
don't need to keep it in sync, and you don't need to touch it again.

⚠️ One important note: saving settings does **not** retroactively change
data already shown on the dashboard — that's from the last completed scan.
Click **Run scan** after saving to actually pull from the new target.

In `backend/.env`, you only need this for the very first run, and only if
you want a default other than the built-in placeholder:
```
DISCOURSE_BASE_URL=https://your-community.example.com
DISCOURSE_API_KEY=
DISCOURSE_API_USERNAME=system
```
No trailing path like `/latest` on `DISCOURSE_BASE_URL` — just the site
root; the client appends `/latest.json`, `/categories.json`, etc. itself.

## The simple way: Docker

You only need [Docker Desktop](https://www.docker.com/products/docker-desktop/)
installed — no Python or Node.js setup on your machine at all. The backend
image is now a plain `python:3.12-slim` base (no browser runtime), so it
builds fast and stays small.

```bash
cd discourse-insights
cp backend/.env.example backend/.env
# edit backend/.env: set ANTHROPIC_API_KEY, DISCOURSE_BASE_URL, DISCOURSE_API_KEY

docker compose up --build
```

- Backend: `http://localhost:8000` (docs at `/docs`)
- Frontend: `http://localhost:5173`

Stop with `Ctrl+C`, restart with `docker compose up` (drop `--build` after
the first run). Fetched data persists between runs in a Docker volume.

## The manual way (no Docker)

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# now edit .env: set ANTHROPIC_API_KEY, DISCOURSE_BASE_URL, DISCOURSE_API_KEY

uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000` (interactive docs at `/docs`).

Key endpoints:
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/scrape` | Kicks off a Discourse fetch + analysis run in the background |
| GET | `/api/scrape/status` | `{ "running": true/false }` — poll this while a scan runs |
| GET | `/api/discourse-settings` | Currently effective Discourse target (persisted save, or `.env` if nothing saved yet) — never exposes the key itself |
| POST | `/api/discourse-settings` | Saves the Discourse target server-side, in the database. Takes effect on the next scan, no rebuild |
| GET | `/api/discourse-categories` | Live category list from Discourse, for the settings dropdown |
| GET | `/api/stats` | Dashboard metric cards |
| GET | `/api/issues` | Ranked issue list from the latest completed run |
| GET | `/api/issues/{id}/posts` | Original source topics behind one issue |

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to
`http://localhost:8000`, so both must be running.

## Deploying to Render

This repo includes a `render.yaml` Blueprint defining both services — the
backend as a Docker web service (now on Render's cheaper, lighter-weight
footprint since there's no Chromium to run), the frontend as a static site.

1. Push this project to a GitHub/GitLab repo.
2. In the Render dashboard: **New → Blueprint**, point it at your repo.
3. Fill in the env vars marked `sync: false`: `ANTHROPIC_API_KEY`,
   `DISCOURSE_BASE_URL`, `DISCOURSE_API_KEY`, `DISCOURSE_API_USERNAME`. You
   can leave `CORS_ORIGINS` / `VITE_API_BASE_URL` blank for now.
4. Deploy, then set `CORS_ORIGINS` on the backend to the frontend's URL, and
   `VITE_API_BASE_URL` on the frontend to the backend's URL + `/api`.

## Using it

1. Click **Run scan**. This calls `POST /api/scrape`, which runs in the
   background: fetch topics from Discourse's API → send batches to Claude
   for clustering & urgency scoring → store the ranked issue list.
2. The dashboard polls scan status every 3s and refreshes when done.
3. Click any row in the issue table to see the original Discourse topics
   grouped into that issue, with links back to the source.
4. Switch languages with the EN/ES/FR/HI toggle — clustering already works
   across languages regardless of the display language.

## How urgency & frequency are computed

- **Frequency** = number of topics in the cluster, weighted slightly by
  their reply counts.
- **Urgency** is decided by Claude per cluster based on impact severity,
  frustration language, and whether a workaround exists — see the prompt
  in `backend/app/analyzer.py` to tune the rubric.

## Notes on scale & rate limits

- Discourse enforces per-key rate limits server-side; `discourse_client.py`
  respects `Retry-After` on 429s and self-throttles between requests
  (`DISCOURSE_REQUEST_DELAY_MS`). Raise `DISCOURSE_MAX_PAGES` for larger
  communities, and consider a scoped key with a higher limit if you scan
  often.
- For production, consider a proper job queue (Celery/RQ) instead of
  `BackgroundTasks`, which won't survive a server restart mid-run.
- `analyzer.py` batches 40 posts per LLM call and consolidates across
  batches; tune `BATCH_SIZE` against your context/cost budget for very
  large scans.
