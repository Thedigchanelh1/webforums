import { useTranslation } from 'react-i18next'
import { Radar, Play, Loader2, Globe, Settings, Globe2 } from 'lucide-react'
import { setLanguage } from '../i18n/index.js'

const LANGS = [
  { code: 'en', label: 'EN' },
  { code: 'es', label: 'ES' },
  { code: 'fr', label: 'FR' },
  { code: 'hi', label: 'HI' },
]

export default function Header({ onScan, scanning, lastRunAt, onOpenSettings, onOpenDiscourseSettings }) {
  const { t, i18n } = useTranslation()

  return (
    <header className="flex flex-col gap-4 border-b border-base-border pb-6 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 text-accent">
          <Radar size={20} strokeWidth={2} />
        </span>
        <div>
          <h1 className="font-display text-xl font-semibold text-ink-primary">{t('app_name')}</h1>
          <p className="text-sm text-ink-muted">{t('tagline')}</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 rounded-lg border border-base-border bg-base-panel p-1">
          <Globe size={14} className="ml-1.5 text-ink-faint" />
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => setLanguage(l.code)}
              className={`rounded-md px-2 py-1 text-xs font-mono transition ${
                i18n.language === l.code
                  ? 'bg-accent/20 text-accent'
                  : 'text-ink-muted hover:text-ink-primary'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        <button
          onClick={onOpenDiscourseSettings}
          title={t('forum_settings')}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-base-border bg-base-panel text-ink-muted transition hover:text-ink-primary"
        >
          <Globe2 size={16} />
        </button>

        <button
          onClick={onOpenSettings}
          title={t('settings')}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-base-border bg-base-panel text-ink-muted transition hover:text-ink-primary"
        >
          <Settings size={16} />
        </button>

        <div className="flex flex-col items-end">
          <button
            onClick={onScan}
            disabled={scanning}
            className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-base transition hover:opacity-90 disabled:opacity-60"
          >
            {scanning ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            {scanning ? t('scanning') : t('run_scan')}
          </button>
          {lastRunAt && (
            <span className="mt-1 font-mono text-[11px] text-ink-faint">
              {t('last_run')}: {new Date(lastRunAt).toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
