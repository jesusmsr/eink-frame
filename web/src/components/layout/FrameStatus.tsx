import { BatteryCharging } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDevice } from '@/hooks/queries'
import { batteryTone, cn, relativeTime } from '@/lib/utils'

const toneBg = {
  good: 'bg-success',
  warning: 'bg-warning',
  critical: 'bg-error',
  unknown: 'bg-ink-300',
}

export function BatteryPill() {
  const { data } = useDevice()
  const pct = data?.battery.percent ?? null
  const tone = batteryTone(pct)
  return (
    <Link
      to="/frame"
      className="flex items-center gap-2 px-3 py-1.5 bg-ink-100 rounded-lg hover:bg-ink-200 transition-colors"
      title="Batería del marco"
    >
      {data?.battery.charging ? (
        <BatteryCharging className="w-5 h-5 text-success" />
      ) : (
        <div className="relative w-7 h-3.5 border-2 border-ink-400 rounded-[3px] after:absolute after:-right-[4px] after:top-[3px] after:w-[2px] after:h-[4px] after:bg-ink-400 after:rounded-r">
          <div
            className={cn('absolute inset-y-0 left-0 rounded-[1px]', toneBg[tone])}
            style={{ width: `${pct == null ? 0 : Math.max(8, pct)}%` }}
          />
        </div>
      )}
      <span className="text-xs font-medium text-ink-600 tabular-nums">{pct == null ? '—' : `${Math.round(pct)}%`}</span>
    </Link>
  )
}

export function FrameStatusCard() {
  const { data } = useDevice()
  const online = data?.online ?? false
  return (
    <Link to="/frame" className="block bg-ink-50 rounded-xl p-4 hover:bg-ink-100 transition-colors">
      <p className="text-xs text-ink-500 mb-1">Estado del marco</p>
      <div className="flex items-center gap-2">
        <span className={cn('w-2 h-2 rounded-full', online ? 'bg-success animate-pulse' : 'bg-ink-300')} />
        <span className="text-sm font-medium text-ink-700">
          {data?.last_seen ? (online ? 'Conectado' : 'Sin noticias') : 'Nunca conectado'}
        </span>
      </div>
      <p className="text-xs text-ink-400 mt-2">Última conexión: {relativeTime(data?.last_seen)}</p>
      {data?.next_expected && (
        <p className="text-xs text-ink-400">Próxima: {relativeTime(data.next_expected)}</p>
      )}
    </Link>
  )
}
