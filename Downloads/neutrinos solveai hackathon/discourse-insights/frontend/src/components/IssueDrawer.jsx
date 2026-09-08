import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ExternalLink, MessageSquare, Loader2 } from 'lucide-react'
import { api } from '../api'

export default function IssueDrawer({ issueId }) {
  const { t } = useTranslation()
  const [posts, setPosts] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .getIssuePosts(issueId)
      .then((data) => !cancelled && setPosts(data))
      .catch((e) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [issueId])

  return (
    <div className="animate-slideDown border-t border-base-border bg-base/60 px-5 py-4">
      <div className="mb-3 text-xs font-medium uppercase tracking-wide text-ink-muted">
        {t('source_posts')}
      </div>

      {error && <p className="text-sm text-urgency-high">{error}</p>}

      {!posts && !error && (
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <Loader2 size={14} className="animate-spin" /> …
        </div>
      )}

      <div className="flex flex-col gap-2">
        {posts?.map((p) => (
          <a
            key={p.id}
            href={p.url}
            target="_blank"
            rel="noreferrer"
            className="group flex flex-col gap-1 rounded-xl border border-base-border bg-base-raised px-4 py-3 transition hover:border-accent/40"
          >
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-medium text-ink-primary group-hover:text-accent">{p.title}</span>
              <ExternalLink size={14} className="mt-0.5 shrink-0 text-ink-faint group-hover:text-accent" />
            </div>
            <p className="line-clamp-2 text-sm text-ink-muted">{p.content}</p>
            <div className="mt-1 flex items-center gap-3 font-mono text-xs text-ink-faint">
              <span>{t('by')} {p.author}</span>
              {p.timestamp && <span>{p.timestamp}</span>}
              <span className="flex items-center gap-1">
                <MessageSquare size={11} /> {p.reply_count} {t('replies')}
              </span>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
