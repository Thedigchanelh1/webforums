import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown } from 'lucide-react'
import UrgencyBadge from './UrgencyBadge'
import IssueDrawer from './IssueDrawer'

const URGENCY_RANK = { High: 0, Medium: 1, Low: 2 }
const URGENCY_BAR_COLOR = { High: 'bg-urgency-high', Medium: 'bg-urgency-medium', Low: 'bg-urgency-low' }

export default function IssueTable({ issues }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(null)
  const [sortBy, setSortBy] = useState('rank') // 'rank' | 'frequency'

  const maxFrequency = useMemo(() => Math.max(1, ...issues.map((i) => i.frequency)), [issues])

  const sorted = useMemo(() => {
    const copy = [...issues]
    if (sortBy === 'frequency') {
      copy.sort((a, b) => b.frequency - a.frequency)
    } else {
      copy.sort((a, b) => URGENCY_RANK[a.urgency] - URGENCY_RANK[b.urgency] || b.frequency - a.frequency)
    }
    return copy
  }, [issues, sortBy])

  return (
    <div className="overflow-hidden rounded-2xl border border-base-border bg-base-panel">
      <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 border-b border-base-border px-5 py-3 text-xs uppercase tracking-wide text-ink-muted">
        <span>{t('table_issue')}</span>
        <button
          onClick={() => setSortBy('rank')}
          className={`transition ${sortBy === 'rank' ? 'text-ink-primary' : 'hover:text-ink-primary'}`}
        >
          {t('table_urgency')}
        </button>
        <button
          onClick={() => setSortBy('frequency')}
          className={`transition ${sortBy === 'frequency' ? 'text-ink-primary' : 'hover:text-ink-primary'}`}
        >
          {t('table_frequency')}
        </button>
        <span className="w-4" />
      </div>

      <div className="divide-y divide-base-border">
        {sorted.map((issue) => {
          const isOpen = expanded === issue.id
          const barHeightPct = Math.max(12, (issue.frequency / maxFrequency) * 100)
          return (
            <div key={issue.id}>
              <button
                onClick={() => setExpanded(isOpen ? null : issue.id)}
                className="grid w-full grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-5 py-4 text-left transition hover:bg-base-raised/60"
              >
                <div className="flex items-start gap-3 min-w-0">
                  <span className="mt-1 h-8 w-1 shrink-0 rounded-full bg-base-border overflow-hidden relative">
                    <span
                      className={`absolute bottom-0 left-0 w-full rounded-full ${URGENCY_BAR_COLOR[issue.urgency]}`}
                      style={{ height: `${barHeightPct}%` }}
                    />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-ink-primary">{issue.title}</p>
                    <p className="truncate text-sm text-ink-muted">{issue.summary}</p>
                  </div>
                </div>

                <UrgencyBadge level={issue.urgency} />

                <span className="font-mono text-sm text-ink-muted tabular-nums">{issue.frequency}</span>

                <ChevronDown
                  size={16}
                  className={`text-ink-faint transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
              </button>
              {isOpen && <IssueDrawer issueId={issue.id} />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
