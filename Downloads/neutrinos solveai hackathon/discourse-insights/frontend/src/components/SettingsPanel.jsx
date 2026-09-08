import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, KeyRound, ExternalLink, Coins, ChevronDown } from 'lucide-react'
import { settingsStore } from '../settingsStore'

export default function SettingsPanel({ open, onClose, providers, onSave }) {
  const { t } = useTranslation()
  const [provider, setProvider] = useState('anthropic')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [customModel, setCustomModel] = useState('')

  const info = useMemo(() => providers.find((p) => p.id === provider), [providers, provider])

  useEffect(() => {
    if (!open || providers.length === 0) return
    const activeProvider = settingsStore.getProvider() || providers[0].id
    const activeInfo = providers.find((p) => p.id === activeProvider) || providers[0]
    setProvider(activeInfo.id)
    setApiKey(settingsStore.getApiKey(activeInfo.id))
    setBaseUrl(settingsStore.getBaseUrl(activeInfo.id, activeInfo.default_base_url || ''))
    const savedModel = settingsStore.getModel(activeInfo.id, activeInfo.models[0]?.id)
    const isKnownModel = activeInfo.models.some((m) => m.id === savedModel)
    setModel(isKnownModel ? savedModel : activeInfo.models[0]?.id)
    setCustomModel(isKnownModel ? '' : savedModel || '')
  }, [open, providers])

  const handleProviderChange = (nextId) => {
    const nextInfo = providers.find((p) => p.id === nextId)
    setProvider(nextId)
    setApiKey(settingsStore.getApiKey(nextId))
    setBaseUrl(settingsStore.getBaseUrl(nextId, nextInfo?.default_base_url || ''))
    const savedModel = settingsStore.getModel(nextId, nextInfo?.models?.[0]?.id)
    const isKnownModel = nextInfo?.models?.some((m) => m.id === savedModel)
    setModel(isKnownModel ? savedModel : nextInfo?.models?.[0]?.id)
    setCustomModel(isKnownModel ? '' : savedModel || '')
  }

  if (!open || !info) return null

  const effectiveModel = info.allow_custom_model && customModel.trim() ? customModel.trim() : model

  const handleSave = () => {
    settingsStore.setProvider(provider)
    settingsStore.setApiKey(provider, apiKey.trim())
    settingsStore.setModel(provider, effectiveModel)
    if (info.base_url_editable) settingsStore.setBaseUrl(provider, baseUrl.trim())
    onSave?.({ provider, apiKey: apiKey.trim(), model: effectiveModel, baseUrl: baseUrl.trim() })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-md rounded-2xl border border-base-border bg-base-panel p-6 shadow-xl">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <KeyRound size={18} className="text-accent" />
            <h2 className="font-display text-lg font-semibold text-ink-primary">{t('settings_title')}</h2>
          </div>
          <button onClick={onClose} className="text-ink-faint hover:text-ink-primary">
            <X size={18} />
          </button>
        </div>

        {/* Provider select */}
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-muted">
          {t('select_processor')}
        </label>
        <div className="relative mb-5">
          <select
            value={provider}
            onChange={(e) => handleProviderChange(e.target.value)}
            className="w-full appearance-none rounded-lg border border-base-border bg-base px-3 py-2 pr-9 text-sm text-ink-primary outline-none focus:border-accent"
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint" />
        </div>

        {/* Per-provider config */}
        <div className="mb-5 rounded-xl border border-base-border bg-base-raised p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-accent">
            {info.label} {t('configuration')}
          </p>

          {info.requires_api_key ? (
            <>
              <label className="mb-1 block text-xs font-medium text-ink-muted">{t('api_key_label')}</label>
              <input
                type="password"
                autoComplete="off"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={t('api_key_placeholder')}
                className="mb-1 w-full rounded-lg border border-base-border bg-base px-3 py-2 font-mono text-sm text-ink-primary outline-none focus:border-accent"
              />
              <div className="mb-4 flex items-center justify-between">
                <span className="text-[11px] text-ink-faint">{t('key_saved_locally')}</span>
                {info.key_help_url && (
                  <a
                    href={info.key_help_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-[11px] text-accent hover:underline"
                  >
                    {t('get_from')} {new URL(info.key_help_url).hostname} <ExternalLink size={11} />
                  </a>
                )}
              </div>
            </>
          ) : (
            <>
              <label className="mb-1 block text-xs font-medium text-ink-muted">{t('base_url_label')}</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={info.default_base_url}
                className="mb-1 w-full rounded-lg border border-base-border bg-base px-3 py-2 font-mono text-sm text-ink-primary outline-none focus:border-accent"
              />
              <p className="mb-4 text-[11px] text-ink-faint">{t('ollama_hint')}</p>
            </>
          )}

          <label className="mb-1 block text-xs font-medium text-ink-muted">{t('model_label')}</label>
          <div className="relative mb-2">
            <select
              value={model}
              onChange={(e) => {
                setModel(e.target.value)
                setCustomModel('')
              }}
              className="w-full appearance-none rounded-lg border border-base-border bg-base px-3 py-2 pr-9 text-sm text-ink-primary outline-none focus:border-accent"
            >
              {info.models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint" />
          </div>

          {info.allow_custom_model && (
            <input
              type="text"
              value={customModel}
              onChange={(e) => setCustomModel(e.target.value)}
              placeholder={t('custom_model_placeholder')}
              className="w-full rounded-lg border border-dashed border-base-border bg-base px-3 py-2 font-mono text-xs text-ink-primary outline-none focus:border-accent"
            />
          )}
        </div>

        {/* Cost hint */}
        <div className="mb-6 flex items-start gap-2 rounded-lg border border-accent/20 bg-accent/10 px-3 py-2.5">
          <Coins size={14} className="mt-0.5 shrink-0 text-accent" />
          <span className="text-xs text-ink-muted">{info.cost_hint}</span>
        </div>

        <button
          onClick={handleSave}
          className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-base transition hover:opacity-90"
        >
          {t('save_configuration')}
        </button>
      </div>
    </div>
  )
}
