export default function MetricCard({ icon: Icon, label, value, accent = 'text-accent', sub }) {
  return (
    <div className="rounded-2xl border border-base-border bg-base-panel p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide text-ink-muted">{label}</span>
        <Icon size={16} className={accent} strokeWidth={2} />
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-display text-3xl font-semibold text-ink-primary tabular-nums">{value}</span>
      </div>
      {sub && <span className="text-xs text-ink-faint font-mono truncate">{sub}</span>}
    </div>
  )
}
