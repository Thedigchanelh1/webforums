const STORAGE_KEY = 'fi_ai_settings'

// Everything here lives only in the browser's localStorage and is sent
// directly to this app's own backend with each scan request — none of it
// is written to disk or a database on the server. Clearing browser data
// or using a private window removes it.
function loadAll() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}
  } catch {
    return {}
  }
}

function saveAll(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

export const settingsStore = {
  getProvider: () => loadAll().provider || 'anthropic',
  setProvider: (provider) => saveAll({ ...loadAll(), provider }),

  getApiKey: (provider) => loadAll().apiKeys?.[provider] || '',
  setApiKey: (provider, key) => {
    const data = loadAll()
    data.apiKeys = { ...(data.apiKeys || {}), [provider]: key }
    saveAll(data)
  },
  clearApiKey: (provider) => {
    const data = loadAll()
    if (data.apiKeys) delete data.apiKeys[provider]
    saveAll(data)
  },

  getModel: (provider, fallback) => loadAll().models?.[provider] || fallback,
  setModel: (provider, model) => {
    const data = loadAll()
    data.models = { ...(data.models || {}), [provider]: model }
    saveAll(data)
  },

  getBaseUrl: (provider, fallback) => loadAll().baseUrls?.[provider] || fallback,
  setBaseUrl: (provider, url) => {
    const data = loadAll()
    data.baseUrls = { ...(data.baseUrls || {}), [provider]: url }
    saveAll(data)
  },

  // Convenience: the full active config for the currently selected provider.
  getActiveConfig: (providerCatalog) => {
    const provider = settingsStore.getProvider()
    const info = providerCatalog?.find((p) => p.id === provider)
    return {
      provider,
      apiKey: settingsStore.getApiKey(provider),
      model: settingsStore.getModel(provider, info?.models?.[0]?.id),
      baseUrl: settingsStore.getBaseUrl(provider, info?.default_base_url),
    }
  },
}
