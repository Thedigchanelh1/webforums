import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Globe2, ChevronDown, Loader2, Check } from 'lucide-react'
import { api } from '../api'

export default function DiscourseSettingsPanel({ open, onClose, defaults, onSave }) {
  const { t } = useTranslation()
  const [discourseBaseUrl, setDiscourseBaseUrl] = useState('')
  const [discourseApiKey, setDiscourseApiKey] = useState('')
  const [discourseApiUsername, setDiscourseApiUsername] = useState('system')
  const [discourseCategoryId, setDiscourseCategoryId] = useState('')
  const [maxPages, setMaxPages] = useState(20)
  const [categories, setCategories] = useState([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  useEffect(() => {
    if (!open) return
    // Always start from whatever's currently effective on the backend
    // (persisted save if one exists, otherwise .env) — never from anything
    // cached in this browser, so there's exactly one source of truth.
    setDiscourseBaseUrl(defaults?.discourse_base_url || '')
    setDiscourseApiKey('')
    setDiscourseApiUsername('system')
    setDiscourseCategoryId(defaults?.discourse_category_id ?? '')
    setMaxPages(defaults?.max_pages ?? 20)
    setSaveError(null)
  }, [open, defaults])

  useEffect(() => {
    if (!open || !discourseBaseUrl) return
    api
      .getDiscourseCategories({ baseUrl: discourseBaseUrl, apiKey: discourseApiKey, apiUsername: discourseApiUsername })
      .then(setCategories)
      .catch(() => setCategories([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, discourseBaseUrl])

  if (!open) return null

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await api.saveDiscourseSettings({
        discourseBaseUrl: discourseBaseUrl.trim(),
        // Blank means "don't touch the saved key" — never sends an empty
        // string that would wipe out a previously configured key.
        discourseApiKey: discourseApiKey.trim() || undefined,
        discourseApiUsername: discourseApiUsername.trim() || 'system',
        discourseCategoryId: discourseCategoryId === '' ? null : Number(discourseCategoryId),
        maxPages: Math.max(1, Math.min(500, Number(maxPages) || 20)),
      })
      onSave?.(updated)
      onClose()
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-md rounded-2xl border border-base-border bg-base-panel p-6 shadow-xl">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <Globe2 size={18} className="text-accent" />
            <h2 className="font-display text-lg font-semibold text-ink-primary">{t('forum_settings_title')}</h2>
          </div>
          <button onClick={onClose} className="text-ink-faint hover:text-ink-primary">
            <X size={18} />
          </button>
        </div>

        <p className="mb-5 text-sm text-ink-muted">{t('forum_settings_body')}</p>

        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-muted">
          {t('forum_url_label')}
        </label>
        <input
          type="text"
          value={discourseBaseUrl}
          onChange={(e) => setDiscourseBaseUrl(e.target.value)}
          placeholder="https://community.example.com"
          className="mb-4 w-full rounded-lg border border-base-border bg-base px-3 py-2 font-mono text-sm text-ink-primary outline-none focus:border-accent"
        />

        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-muted">
          {t('discourse_api_key_label')}
        </label>
        <input
          type="password"
          value={discourseApiKey}
          onChange={(e) => setDiscourseApiKey(e.target.value)}
          placeholder={t('discourse_api_key_placeholder')}
          className="mb-1 w-full rounded-lg border border-base-border bg-base px-3 py-2 font-mono text-sm text-ink-primary outline-none focus:border-accent"
        />
        <p className="mb-4 flex items-center gap-1 text-[11px] text-ink-faint">
          {defaults?.api_key_configured && (
            <>
              <Check size={12} className="text-accent" /> {t('discourse_api_key_configured')}
            </>
          )}
          {!defaults?.api_key_configured && t('discourse_api_key_hint', { base_url: discourseBaseUrl || 'https://your-forum' })}
        </p>

        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-muted">
          {t('discourse_api_username_label')}
        </label>
        <input
          type="text"
          value={discourseApiUsername}
          onChange={(e) => setDiscourseApiUsername(e.target.value)}
          placeholder="system"
          className="mb-4 w-full rounded-lg border border-base-border bg-base px-3 py-2 font-mono text-sm text-ink-primary outline-none focus:border-accent"
        />

        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-muted">
          {t('discourse_category_label')}
        </label>
        <div className="relative mb-4">
          <select
            value={discourseCategoryId}
            onChange={(e) => setDiscourseCategoryId(e.target.value)}
            className="w-full appearance-none rounded-lg border border-base-border bg-base px-3 py-2 pr-9 text-sm text-ink-primary outline-none focus:border-accent"
          >
            <option value="">{t('discourse_category_all')}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.topic_count})
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint" />
        </div>

        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-muted">
          {t('max_pages_label')}
        </label>
        <input
          type="number"
          min={1}
          max={500}
          value={maxPages}
          onChange={(e) => setMaxPages(e.target.value)}
          className="mb-1 w-full rounded-lg border border-base-border bg-base px-3 py-2 font-mono text-sm text-ink-primary outline-none focus:border-accent"
        />
        <p className="mb-6 text-[11px] text-ink-faint">{t('max_pages_hint')}</p>

        {saveError && (
          <p className="mb-4 rounded-lg border border-urgency-high/30 bg-urgency-highSoft px-3 py-2 text-xs text-urgency-high">
            {saveError}
          </p>
        )}

        <button
          onClick={handleSave}
          disabled={saving || !discourseBaseUrl.trim()}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-base transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          {t('save_configuration')}
        </button>
        <p className="mt-3 text-center text-[11px] text-ink-faint">
          Saved to the backend immediately — no rebuild needed. Click "Run scan" after saving to pull fresh data.
        </p>
      </div>
    </div>
  )
}
