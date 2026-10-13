import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Palette, Save, Send } from 'lucide-react'
import { Alert, Button, Card } from '@/components/ui'
import { keys, useReprocess, useSettings, useSettingsMeta } from '@/hooks/queries'
import { api, errorMessage, type FrameSettings } from '@/lib/api'
import { cn } from '@/lib/utils'

const COLOR_LABELS: Record<string, string> = {
  black: 'Negro',
  white: 'Blanco',
  green: 'Verde',
  blue: 'Azul',
  red: 'Rojo',
  yellow: 'Amarillo',
  orange: 'Naranja',
}

const ROTATIONS = [
  { value: 3, label: 'Vertical' },
  { value: 1, label: 'Vertical (180°)' },
  { value: 0, label: 'Horizontal' },
  { value: 2, label: 'Horizontal (180°)' },
]

export function SettingsPage() {
  const qc = useQueryClient()
  const { data: saved, error: loadError } = useSettings()
  const { data: meta } = useSettingsMeta()
  const [form, setForm] = useState<FrameSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [watchReprocess, setWatchReprocess] = useState(false)
  const { data: reprocess } = useReprocess(watchReprocess)

  useEffect(() => {
    if (saved && !form) setForm(saved)
  }, [saved, form])

  useEffect(() => {
    if (watchReprocess && reprocess && !reprocess.running) {
      setWatchReprocess(false)
      qc.invalidateQueries({ queryKey: keys.images })
    }
  }, [reprocess, watchReprocess, qc])

  if (loadError) return <Alert variant="error">{errorMessage(loadError)}</Alert>
  if (!form || !meta) return <Loader2 className="w-6 h-6 animate-spin text-ink-400 mx-auto mt-12" />

  const set = <K extends keyof FrameSettings>(k: K, v: FrameSettings[K]) => setForm({ ...form, [k]: v })
  const dirty = JSON.stringify(form) !== JSON.stringify(saved)

  const save = async () => {
    setSaving(true)
    setMsg(null)
    try {
      const res = await api<FrameSettings>('/api/settings', { method: 'PUT', json: form })
      qc.setQueryData(keys.settings, res)
      setForm(res)
      setWatchReprocess(true)
      qc.invalidateQueries({ queryKey: keys.reprocess })
      setMsg({ ok: true, text: 'Ajustes guardados. El marco los aplicará en su próxima conexión.' })
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  const sendCalibration = async () => {
    setMsg(null)
    try {
      await api('/api/images/calibration', { method: 'POST' })
      qc.invalidateQueries({ queryKey: keys.images })
      qc.invalidateQueries({ queryKey: keys.device })
      setMsg({ ok: true, text: 'Carta de calibración en cola: saldrá en la próxima conexión. Luego puedes borrarla de la galería.' })
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) })
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink-900">Ajustes</h1>
        <p className="text-ink-500 mt-1">El marco recibe estos ajustes en cada conexión: no hace falta reflashearlo.</p>
      </div>

      {msg && (
        <Alert variant={msg.ok ? 'success' : 'error'} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}
      {reprocess?.running && (
        <Alert variant="info">
          Regenerando imágenes con los nuevos ajustes… {reprocess.done}/{reprocess.total}
        </Alert>
      )}

      <Card>
        <Card.Header title="Rotación de fotos" />
        <div className="grid sm:grid-cols-2 gap-5">
          <NumberField label="Cada foto se muestra" suffix="min" min={5} max={1440} value={form.interval_minutes} onChange={(v) => set('interval_minutes', v)} />
          <NumberField
            label="Comprobar la cola como máximo cada"
            suffix="min"
            min={5}
            max={form.interval_minutes}
            value={form.check_minutes}
            onChange={(v) => set('check_minutes', v)}
            help="Menos minutos = «Mostrar a continuación» llega antes, pero gasta más batería."
          />
          <Field label="Orden">
            <select className={inputCls} value={form.order} onChange={(e) => set('order', e.target.value as FrameSettings['order'])}>
              <option value="shuffle">Aleatorio sin repetir</option>
              <option value="random">Aleatorio puro</option>
              <option value="sequential">Por fecha de subida</option>
            </select>
          </Field>
        </div>
      </Card>

      <Card>
        <Card.Header title="Horas de silencio" subtitle="El marco no se actualiza en esta franja y duerme de un tirón (ahorra batería)." />
        <label className="flex items-center gap-3 text-sm text-ink-700 mb-4 cursor-pointer">
          <input type="checkbox" className="w-5 h-5 accent-accent-500" checked={form.quiet_enabled} onChange={(e) => set('quiet_enabled', e.target.checked)} />
          Activar
        </label>
        <div className={cn('grid grid-cols-2 gap-5', !form.quiet_enabled && 'opacity-50 pointer-events-none')}>
          <Field label="Desde">
            <input type="time" className={inputCls} value={form.quiet_start} onChange={(e) => set('quiet_start', e.target.value)} />
          </Field>
          <Field label="Hasta">
            <input type="time" className={inputCls} value={form.quiet_end} onChange={(e) => set('quiet_end', e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card>
        <Card.Header title="Imagen" subtitle="Cambiar estos valores regenera todas las imágenes." />
        <div className="space-y-5">
          <Field label="Orientación del marco">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {ROTATIONS.map((r) => (
                <button
                  key={r.value}
                  onClick={() => set('rotation', r.value)}
                  className={cn(
                    'px-3 py-2 rounded-lg border-2 text-sm font-medium',
                    form.rotation === r.value ? 'border-ink-900 bg-ink-900 text-white' : 'border-ink-200 text-ink-600 hover:border-ink-400',
                  )}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </Field>
          <Slider label="Saturación" min={0.5} max={2} step={0.05} value={form.saturation} onChange={(v) => set('saturation', v)} />
          <Slider label="Contraste" min={0.5} max={2} step={0.05} value={form.contrast} onChange={(v) => set('contrast', v)} />
          <Slider label="Brillo" min={0.5} max={1.5} step={0.05} value={form.brightness} onChange={(v) => set('brightness', v)} />
          <Field label="Tramado (dithering)">
            <select className={inputCls} value={form.dither} onChange={(e) => set('dither', e.target.value as FrameSettings['dither'])}>
              <option value="floyd_steinberg">Floyd–Steinberg (recomendado para fotos)</option>
              <option value="none">Sin tramado (ilustraciones planas)</option>
            </select>
          </Field>
        </div>
      </Card>

      <Card>
        <Card.Header
          title="Paleta del panel"
          subtitle="Colores reales que muestra tu panel. Envía la carta de calibración, fotografíala con luz natural y ajusta cada color al que veas."
          action={<Palette className="w-5 h-5 text-ink-400" />}
        />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {meta.palette_names.map((name, i) => (
            <label key={name} className="flex items-center gap-2 p-2 rounded-lg border border-ink-200">
              <input
                type="color"
                value={form.palette[i]}
                onChange={(e) => set('palette', form.palette.map((c, j) => (j === i ? e.target.value : c)))}
                className="w-9 h-9 rounded cursor-pointer border-0 bg-transparent"
              />
              <span className="text-sm">
                <span className="block font-medium text-ink-700">{COLOR_LABELS[name] ?? name}</span>
                <span className="font-mono text-xs text-ink-400">{form.palette[i]}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <Button variant="outline" size="sm" onClick={() => set('palette', meta.palette_default)}>
            Paleta realista
          </Button>
          <Button variant="outline" size="sm" onClick={() => set('palette', meta.palette_ideal)}>
            Colores puros
          </Button>
          <Button variant="secondary" size="sm" onClick={sendCalibration}>
            <Send className="w-4 h-4 mr-1.5" /> Enviar carta de calibración
          </Button>
        </div>
      </Card>

      <Card>
        <Card.Header title="Batería" />
        <div className="grid sm:grid-cols-2 gap-5">
          <NumberField
            label="Batería baja"
            suffix="mV"
            min={3000}
            max={4000}
            value={form.battery_low_mv}
            onChange={(v) => set('battery_low_mv', v)}
            help={`Por debajo, el intervalo se multiplica ×${form.low_battery_interval_factor}.`}
          />
          <NumberField
            label="Batería crítica"
            suffix="mV"
            min={3000}
            max={3800}
            value={form.battery_critical_mv}
            onChange={(v) => set('battery_critical_mv', v)}
            help="Por debajo, el marco muestra el aviso y deja de despertarse hasta que lo cargues."
          />
          <Slider
            label="Multiplicador con batería baja"
            min={1}
            max={6}
            step={0.5}
            value={form.low_battery_interval_factor}
            onChange={(v) => set('low_battery_interval_factor', v)}
          />
          <Field label="Factor de calibración del ADC">
            <p className="text-sm text-ink-700 font-mono pt-2">{form.battery_factor.toFixed(4)}</p>
            <p className="text-xs text-ink-500">Se ajusta desde Marco → Calibrar batería.</p>
          </Field>
        </div>
      </Card>

      <div className="sticky bottom-20 lg:bottom-4 flex justify-end gap-3">
        {dirty && (
          <Button variant="outline" onClick={() => setForm(saved ?? null)} className="bg-white">
            Descartar
          </Button>
        )}
        <Button onClick={save} isLoading={saving} disabled={!dirty} className="shadow-soft">
          <Save className="w-4 h-4 mr-2" /> Guardar
        </Button>
      </div>
    </div>
  )
}

const inputCls =
  'w-full px-3 py-2 bg-white border border-ink-300 rounded-lg text-ink-900 focus:outline-none focus:ring-2 focus:ring-accent-500'

function Field({ label, children, help }: { label: string; children: React.ReactNode; help?: string }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium text-ink-700">{label}</p>
      {children}
      {help && <p className="text-xs text-ink-500">{help}</p>}
    </div>
  )
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  suffix,
  help,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  suffix: string
  help?: string
}) {
  return (
    <Field label={label} help={help}>
      <div className="flex items-center gap-2">
        <input
          type="number"
          className={inputCls}
          min={min}
          max={max}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <span className="text-sm text-ink-500">{suffix}</span>
      </div>
    </Field>
  )
}

function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step: number
}) {
  return (
    <div>
      <div className="flex justify-between text-sm">
        <span className="font-medium text-ink-700">{label}</span>
        <span className="font-mono text-ink-500">{value.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-accent-500"
      />
    </div>
  )
}
