import { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  AlertTriangle,
  BatteryCharging,
  BatteryFull,
  BatteryLow,
  BatteryMedium,
  Clock,
  Gauge,
  Moon,
  Wifi,
} from 'lucide-react'
import { Alert, Button, Card, Input } from '@/components/ui'
import { keys, useDevice, useImages, useReports, useSettings } from '@/hooks/queries'
import { api, errorMessage, imageUrl } from '@/lib/api'
import { batteryTone, cn, formatDate, formatDuration, formatTime, formatVolts, relativeTime, rssiLabel } from '@/lib/utils'

const RANGES = [
  { hours: 24, label: '24 h' },
  { hours: 24 * 7, label: '7 días' },
  { hours: 24 * 30, label: '30 días' },
]

const toneText = {
  good: 'text-green-700',
  warning: 'text-yellow-700',
  critical: 'text-red-700',
  unknown: 'text-ink-500',
}

export function FramePage() {
  const { data: device, error } = useDevice()
  const { data: images = [] } = useImages()
  const { data: settings } = useSettings()
  const [hours, setHours] = useState(24 * 7)
  const { data: reports = [] } = useReports(hours)

  const current = images.find((i) => i.id === device?.current_image_id)
  const queue = (device?.queue ?? []).map((id) => images.find((i) => i.id === id)).filter(Boolean)
  const b = device?.battery
  const tone = batteryTone(b?.percent)
  const BatteryIcon = b?.charging ? BatteryCharging : tone === 'good' ? BatteryFull : tone === 'warning' ? BatteryMedium : BatteryLow
  const vertical = settings ? settings.rotation % 2 === 1 : true

  const chart = useMemo(
    () =>
      reports
        .filter((r) => r.percent != null)
        .map((r) => ({
          t: new Date(r.ts).getTime(),
          percent: r.percent,
          volts: r.battery_mv != null ? r.battery_mv / 1000 : null,
        })),
    [reports],
  )
  const awake = useMemo(
    () => reports.filter((r) => r.awake_ms != null).map((r) => ({ t: new Date(r.ts).getTime(), s: (r.awake_ms ?? 0) / 1000, status: r.status })),
    [reports],
  )
  const tickFormat = (t: number) =>
    hours <= 24 ? formatTime(new Date(t).toISOString()) : new Date(t).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink-900">Marco</h1>
        <p className="text-ink-500 mt-1">Estado, batería y lo que se está mostrando.</p>
      </div>

      {error && <Alert variant="error">{errorMessage(error)}</Alert>}
      {b?.critical && (
        <Alert variant="error">Batería crítica ({formatVolts(b.mv)}). El marco dejará de actualizarse para proteger la batería: cárgalo.</Alert>
      )}
      {b?.low && !b.critical && <Alert variant="warning">Batería baja: el marco está espaciando las actualizaciones.</Alert>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat
          icon={<span className={cn('w-2.5 h-2.5 rounded-full', device?.online ? 'bg-success' : 'bg-ink-300')} />}
          label="Conexión"
          value={device?.last_seen ? (device.online ? 'Conectado' : 'Sin noticias') : 'Nunca'}
          sub={
            <>
              Última {relativeTime(device?.last_seen)}
              {device?.next_expected && <> · próxima {relativeTime(device.next_expected)}</>}
            </>
          }
        />
        <Stat
          icon={<BatteryIcon className={cn('w-5 h-5', toneText[tone])} />}
          label="Batería"
          value={b?.percent != null ? `${Math.round(b.percent)}%` : '—'}
          sub={
            <>
              {formatVolts(b?.mv)}
              {b?.charging ? ' · cargando' : b?.days_left != null ? ` · ~${b.days_left} días` : ''}
            </>
          }
        />
        <Stat icon={<Wifi className="w-5 h-5 text-ink-500" />} label="WiFi" value={rssiLabel(device?.rssi).split(' (')[0]} sub={device?.rssi != null ? `${device.rssi} dBm` : '—'} />
        <Stat
          icon={<Gauge className="w-5 h-5 text-ink-500" />}
          label="Despierto por ciclo"
          value={formatDuration(device?.awake_ms_avg)}
          sub={`${device?.reports_24h ?? 0} conexiones en 24 h · fw ${device?.fw ?? '—'}`}
        />
      </div>

      <div className={cn('grid gap-6', vertical ? 'md:grid-cols-[auto_1fr]' : 'grid-cols-1')}>
        <Card>
          <Card.Header title="En pantalla" subtitle={current ? current.original_name : 'Nada todavía'} />
          <div
            className={cn(
              'mx-auto rounded-lg border-[10px] border-ink-800 overflow-hidden bg-ink-100',
              vertical ? 'w-[14rem] aspect-[480/800]' : 'w-full max-w-lg aspect-[800/480]',
            )}
          >
            {current && <img src={imageUrl(current, 'preview')} alt="" className="w-full h-full object-cover [image-rendering:pixelated]" />}
          </div>
          {device?.current_since && (
            <p className="text-xs text-ink-500 mt-3 text-center">
              Desde {formatTime(device.current_since)}
              {device.next_change && <> · cambia hacia las {formatTime(device.next_change)}</>}
            </p>
          )}
        </Card>

        <div className="space-y-6 min-w-0">
          <Card>
            <Card.Header
              title="Batería"
              subtitle="Porcentaje estimado con la curva de descarga LiPo"
              action={
                <div className="flex bg-ink-100 rounded-lg p-1 text-xs">
                  {RANGES.map((r) => (
                    <button
                      key={r.hours}
                      onClick={() => setHours(r.hours)}
                      className={cn('px-2.5 py-1 rounded-md font-medium', hours === r.hours ? 'bg-white shadow-sm text-ink-900' : 'text-ink-500')}
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              }
            />
            <div className="h-64">
              {chart.length > 1 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chart} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                    <defs>
                      <linearGradient id="batFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="#e9ecef" />
                    <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={tickFormat} stroke="#adb5bd" fontSize={11} tickLine={false} axisLine={false} minTickGap={40} />
                    <YAxis domain={[0, 100]} unit="%" stroke="#adb5bd" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip
                      labelFormatter={(t) => formatDate(new Date(t as number).toISOString())}
                      formatter={(_v, _n, item) => [`${Math.round(item.payload.percent)}% · ${item.payload.volts?.toFixed(2)} V`, 'Batería']}
                      contentStyle={{ borderRadius: 8, border: '1px solid #dee2e6', fontSize: 12 }}
                    />
                    <Area type="monotone" dataKey="percent" stroke="#d97706" strokeWidth={2} fill="url(#batFill)" dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <Empty>Aún no hay suficientes lecturas de batería.</Empty>
              )}
            </div>
          </Card>

          <Card>
            <Card.Header title="Tiempo despierto por conexión" subtitle="Cuanto menos, más dura la batería. Un ciclo sin cambio de foto debería rondar 1–3 s." />
            <div className="h-40">
              {awake.length > 1 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={awake} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#e9ecef" />
                    <XAxis dataKey="t" tickFormatter={tickFormat} stroke="#adb5bd" fontSize={11} tickLine={false} axisLine={false} minTickGap={40} />
                    <YAxis unit=" s" stroke="#adb5bd" fontSize={11} tickLine={false} axisLine={false} />
                    <Tooltip
                      labelFormatter={(t) => formatDate(new Date(t as number).toISOString())}
                      formatter={(v) => [`${Number(v).toFixed(1)} s`, 'Despierto (ciclo anterior)']}
                      contentStyle={{ borderRadius: 8, border: '1px solid #dee2e6', fontSize: 12 }}
                    />
                    <Bar dataKey="s" fill="#495057" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty>Sin datos todavía.</Empty>
              )}
            </div>
          </Card>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <Card.Header title="Cola" subtitle="Se mostrarán en este orden, una por conexión" />
          {queue.length === 0 ? (
            <p className="text-sm text-ink-400">Vacía. Usa «Mostrar a continuación» en la galería.</p>
          ) : (
            <ol className="space-y-2">
              {queue.map((img, i) => (
                <li key={img!.id} className="flex items-center gap-3 text-sm">
                  <span className="w-6 text-ink-400 tabular-nums">{i + 1}.</span>
                  <img src={imageUrl(img!, 'thumb')} alt="" className="w-8 h-12 object-cover rounded" />
                  <span className="truncate text-ink-700">{img!.original_name}</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
        <CalibrateBattery lastMv={b?.mv ?? null} />
      </div>

      <Card padding="none">
        <div className="p-6 pb-2">
          <Card.Header title="Últimas conexiones" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-ink-400 uppercase">
              <tr className="border-b border-ink-100">
                <th className="text-left font-medium px-6 py-2">Hora</th>
                <th className="text-left font-medium px-3 py-2">Resultado</th>
                <th className="text-right font-medium px-3 py-2">Batería</th>
                <th className="text-right font-medium px-3 py-2">WiFi</th>
                <th className="text-right font-medium px-3 py-2">Despierto</th>
                <th className="text-right font-medium px-6 py-2">Duerme</th>
              </tr>
            </thead>
            <tbody>
              {[...reports].reverse().slice(0, 25).map((r) => (
                <tr key={r.ts} className="border-b border-ink-50 text-ink-700">
                  <td className="px-6 py-2 whitespace-nowrap">{formatDate(r.ts)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {r.status === 200 ? 'Imagen nueva' : r.status === 304 ? 'Sin cambios' : 'Sin imágenes'}
                    {r.wake_reason && r.wake_reason !== 'timer' && (
                      <span className="ml-2 inline-flex items-center gap-1 text-xs text-yellow-700">
                        <AlertTriangle className="w-3 h-3" /> {r.wake_reason}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatVolts(r.battery_mv)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{r.rssi ?? '—'}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{formatDuration(r.awake_ms)}</td>
                  <td className="px-6 py-2 text-right tabular-nums whitespace-nowrap">
                    {r.sleep_s >= 3600 ? <Moon className="inline w-3 h-3 mr-1 text-ink-400" /> : <Clock className="inline w-3 h-3 mr-1 text-ink-400" />}
                    {Math.round(r.sleep_s / 60)} min
                  </td>
                </tr>
              ))}
              {reports.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-ink-400">
                    El marco todavía no se ha conectado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function Stat({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub: React.ReactNode }) {
  return (
    <Card padding="sm">
      <div className="flex items-center gap-2 text-xs font-medium text-ink-500 uppercase tracking-wide">
        {icon}
        {label}
      </div>
      <p className="text-2xl font-bold text-ink-900 mt-2">{value}</p>
      <p className="text-xs text-ink-500 mt-1">{sub}</p>
    </Card>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="h-full flex items-center justify-center text-sm text-ink-400">{children}</div>
}

function CalibrateBattery({ lastMv }: { lastMv: number | null }) {
  const qc = useQueryClient()
  const [value, setValue] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMsg(null)
    try {
      const v = parseFloat(value.replace(',', '.'))
      const mv = v < 10 ? Math.round(v * 1000) : Math.round(v)
      await api('/api/device/calibrate-battery', { method: 'POST', json: { measured_mv: mv } })
      setMsg({ ok: true, text: 'Calibrado. Las próximas lecturas usarán el nuevo factor.' })
      setValue('')
      qc.invalidateQueries({ queryKey: keys.device })
      qc.invalidateQueries({ queryKey: keys.settings })
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <Card.Header
        title="Calibrar batería"
        subtitle="Mide la batería con el multímetro justo después de que el marco se conecte e introduce el valor."
      />
      <form onSubmit={submit} className="flex gap-3 items-end">
        <div className="flex-1">
          <Input
            label={`Lectura del multímetro (el marco dice ${formatVolts(lastMv)})`}
            placeholder="3,92"
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          />
        </div>
        <Button type="submit" isLoading={loading}>
          Calibrar
        </Button>
      </form>
      {msg && <Alert variant={msg.ok ? 'success' : 'error'} className="mt-3">{msg.text}</Alert>}
    </Card>
  )
}
