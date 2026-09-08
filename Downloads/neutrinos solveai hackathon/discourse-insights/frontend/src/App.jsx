import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Files, ShieldAlert, TrendingUp, Radar, KeyRound } from 'lucide-react'
import Header from './components/Header'
import MetricCard from './components/MetricCard'
import IssueTable from './components/IssueTable'
import SettingsPanel from './components/SettingsPanel'
import DiscourseSettingsPanel from './components/DiscourseSettingsPanel'
import { api } from './api'
import { settingsStore } from './settingsStore'

export default function App() {
  const { t } = useTranslation()
  const [stats, setStats] = useState(null)
  const [issues, setIssues] = useState([])
  const [providers, setProviders] = useState([])
  const [discourseDefaults, setDiscourseDefaults] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [discourseSettingsOpen, setDiscourseSettingsOpen] = useState(false)
  const [discourseJustSaved, setDiscourseJustSaved] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [s, i] = await Promise.all([api.getStats(), api.getIssues()])
      setStats(s)
      setIssues(i)
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    refresh()
    api.getProviders().then(setProviders).catch((e) => setError(`Could not reach backend: ${e.message}`))
    api.getDiscourseSettings().then(setDiscourseDefaults).catch(() => {})
  }, [refresh])

  // Poll while a scan is running so the dashboard updates itself when it finishes.
  useEffect(() => {
    if (!scanning) return
    const interval = setInterval(async () => {
      const status = await api.getScrapeStatus()
      if (!status.running) {
        setScanning(false)
        clearInterval(interval)
        const last = await api.getLastRun()
        if (last.status?.startsWith('failed')) {
          setError(`${t('run_failed')}: ${last.error}`)
        } else {
          setError(null)
        }
        refresh()
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [scanning, refresh, t])

  const handleScan = async () => {
    if (providers.length === 0) {
      setError('Could not load AI provider list from the backend — check that the backend is running and reachable.')
      return
    }
    const config = settingsStore.getActiveConfig(providers)
    const info = providers.find((p) => p.id === config.provider)

    if (info?.requires_api_key && !config.apiKey) {
      setSettingsOpen(true)
      setError(t('key_required_body'))
      return
    }

    try {
      setError(null)
      setScanning(true)
      setDiscourseJustSaved(false)
      await api.triggerScrape({
        provider: config.provider,
        apiKey: config.apiKey,
        model: config.model,
        llmBaseUrl: config.baseUrl,
      })
    } catch (e) {
      setError(e.message)
      setScanning(false)
    }
  }

  // What a scan will actually hit right now — resolved server-side (a saved
  // persisted override if one exists, otherwise backend/.env). This is the
  // single source of truth; there's no browser-side copy to fall out of sync.
  const activeDiscourseUrl = discourseDefaults?.discourse_base_url

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-6 py-10">
      <Header
        onScan={handleScan}
        scanning={scanning}
        lastRunAt={stats?.last_run_at}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenDiscourseSettings={() => setDiscourseSettingsOpen(true)}
      />

      {activeDiscourseUrl && (
        <button
          onClick={() => setDiscourseSettingsOpen(true)}
          className="-mt-4 flex w-fit items-center gap-2 rounded-full border border-base-border bg-base-panel px-3 py-1.5 text-xs text-ink-muted transition hover:border-accent hover:text-ink-primary"
          title="Click to change which Discourse community scans pull from"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Source: <span className="font-mono text-ink-primary">{activeDiscourseUrl}</span>
          <span className="text-ink-faint">· change</span>
        </button>
      )}
      {discourseJustSaved && (
        <p className="-mt-6 text-xs text-accent">Saved — click "Run scan" to pull fresh data from this source.</p>
      )}

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        providers={providers}
        onSave={() => setError(null)}
      />

      <DiscourseSettingsPanel
        open={discourseSettingsOpen}
        onClose={() => setDiscourseSettingsOpen(false)}
        defaults={discourseDefaults}
        onSave={(updated) => {
          setError(null)
          // The save endpoint returns the newly-effective settings directly
          // — no need to re-fetch, and no local cache to keep in sync.
          setDiscourseDefaults(updated)
          setDiscourseJustSaved(true)
        }}
      />

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-urgency-high/30 bg-urgency-highSoft px-4 py-3 text-sm text-urgency-high">
          <KeyRound size={14} className="shrink-0" />
          {error}
        </div>
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard icon={Files} label={t('metric_total_posts')} value={stats?.total_posts ?? '—'} />
        <MetricCard
          icon={ShieldAlert}
          label={t('metric_critical')}
          value={stats?.critical_issues ?? '—'}
          accent="text-urgency-high"
        />
        <MetricCard
          icon={TrendingUp}
          label={t('metric_trends')}
          value={stats?.common_trends?.[0] ?? '—'}
          sub={stats?.common_trends?.slice(1).join(' · ')}
        />
      </section>

      {issues.length > 0 ? (
        <IssueTable issues={issues} />
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-base-border py-16 text-center">
          <Radar size={28} className="text-ink-faint" />
          <p className="font-display text-lg text-ink-primary">{t('no_issues_title')}</p>
          <p className="max-w-sm text-sm text-ink-muted">{t('no_issues_body')}</p>
        </div>
      )}
    </div>
  )
}
