// In plain `npm run dev`, Vite's proxy (vite.config.js) forwards "/api" to
// localhost:8000, so no env var is needed. In Docker or on Render, the
// frontend and backend are separate hosts, so VITE_API_BASE_URL points
// straight at the deployed backend, e.g. https://discourse-insights-backend.onrender.com/api
const BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request to ${path} failed (${res.status})`)
  }
  return res.json()
}

export const api = {
  getStats: () => req('/stats'),
  getIssues: () => req('/issues'),
  getIssuePosts: (issueId) => req(`/issues/${issueId}/posts`),
  getScrapeStatus: () => req('/scrape/status'),
  getLastRun: () => req('/scrape/last'),
  getProviders: () => req('/providers'),
  getDiscourseSettings: () => req('/discourse-settings'),
  saveDiscourseSettings: ({ discourseBaseUrl, discourseApiKey, discourseApiUsername, discourseCategoryId, maxPages }) =>
    req('/discourse-settings', {
      method: 'POST',
      body: JSON.stringify({
        discourse_base_url: discourseBaseUrl,
        discourse_api_key: discourseApiKey,
        discourse_api_username: discourseApiUsername,
        discourse_category_id: discourseCategoryId,
        max_pages: maxPages,
      }),
    }),
  getDiscourseCategories: ({ baseUrl, apiKey, apiUsername }) => {
    const params = new URLSearchParams()
    if (baseUrl) params.set('base_url', baseUrl)
    if (apiKey) params.set('api_key', apiKey)
    if (apiUsername) params.set('api_username', apiUsername)
    return req(`/discourse-categories?${params.toString()}`)
  },
  triggerScrape: ({ provider, apiKey, model, llmBaseUrl, fetchFullContent = false }) =>
    req('/scrape', {
      method: 'POST',
      body: JSON.stringify({
        ai_provider: provider,
        api_key: apiKey,
        model,
        llm_base_url: llmBaseUrl,
        fetch_full_content: fetchFullContent,
        // No discourse_* fields here on purpose — the backend resolves the
        // target Discourse instance itself from what was saved via the
        // settings panel (persisted server-side), falling back to .env.
        // This is what lets you change forum/key without ever rebuilding.
      }),
    }),
}
