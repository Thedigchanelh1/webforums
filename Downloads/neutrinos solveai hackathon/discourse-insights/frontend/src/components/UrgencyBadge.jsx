import { useTranslation } from 'react-i18next'
import { Flame, TriangleAlert, CircleCheck } from 'lucide-react'

// Urgency is encoded with color AND shape/icon (not text alone) so the
// dashboard reads correctly for colorblind users and across languages.
const CONFIG = {
  High: {
    labelKey: 'urgency_high',
    icon: Flame,
    text: 'text-urgency-high',
    dot: 'bg-urgency-high',
    bg: 'bg-urgency-highSoft',
    ring: 'ring-urgency-high/30',
    pulse: true,
  },
  Medium: {
    labelKey: 'urgency_medium',
    icon: TriangleAlert,
    text: 'text-urgency-medium',
    dot: 'bg-urgency-medium',
    bg: 'bg-urgency-mediumSoft',
    ring: 'ring-urgency-medium/30',
    pulse: false,
  },
  Low: {
    labelKey: 'urgency_low',
    icon: CircleCheck,
    text: 'text-urgency-low',
    dot: 'bg-urgency-low',
    bg: 'bg-urgency-lowSoft',
    ring: 'ring-urgency-low/30',
    pulse: false,
  },
}

export default function UrgencyBadge({ level }) {
  const { t } = useTranslation()
  const cfg = CONFIG[level] || CONFIG.Low
  const Icon = cfg.icon
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${cfg.bg} ${cfg.text} ${cfg.ring}`}
    >
      <span className={`relative flex h-1.5 w-1.5 rounded-full ${cfg.dot}`}>
        {cfg.pulse && (
          <span className={`absolute inline-flex h-full w-full rounded-full ${cfg.dot} animate-pulseDot`} />
        )}
      </span>
      <Icon size={12} strokeWidth={2.5} />
      {t(cfg.labelKey)}
    </span>
  )
}
