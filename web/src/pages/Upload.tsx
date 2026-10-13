import { useCallback, useEffect, useRef, useState } from 'react'
import Cropper, { type Area } from 'react-easy-crop'
import { Link } from 'react-router-dom'
import { Check, Clock, ImagePlus, Loader2, RotateCcw, Upload, X } from 'lucide-react'
import { Alert, Button, Card } from '@/components/ui'
import { useDevice, useSettings, useUpload } from '@/hooks/queries'
import { api, errorMessage } from '@/lib/api'
import { cn, frameAspect, relativeTime } from '@/lib/utils'

const MAX_MB = 25

/** Recorta en el navegador a la resolución lógica del panel (para la vista previa rápida) */
async function cropToCanvas(src: string, area: Area, rotation: number): Promise<Blob> {
  const img = new Image()
  img.src = src
  await img.decode()
  const [w, h] = rotation === 0 || rotation === 2 ? [800, 480] : [480, 800]
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(img, area.x, area.y, area.width, area.height, 0, 0, w, h)
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('No se pudo generar la vista previa'))), 'image/png'),
  )
}

export function UploadPage() {
  const { data: settings } = useSettings()
  const { data: device } = useDevice()
  const upload = useUpload()
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const accept = (list: FileList | null) => {
    if (!list) return
    const imgs = Array.from(list).filter((f) => f.type.startsWith('image/'))
    const tooBig = imgs.find((f) => f.size > MAX_MB * 1024 * 1024)
    if (tooBig) {
      setError(`"${tooBig.name}" supera los ${MAX_MB} MB`)
      return
    }
    if (!imgs.length) {
      setError('Selecciona una o varias imágenes')
      return
    }
    setError('')
    setDone('')
    setFiles(imgs)
  }

  const reset = (message = '') => {
    setFiles([])
    setDone(message)
    if (inputRef.current) inputRef.current.value = ''
  }

  const nextWake = device?.next_expected ? relativeTime(device.next_expected) : null

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-ink-900">Subir imagen</h1>
        <p className="text-ink-500 mt-1">Recórtala, comprueba cómo quedará en el panel de 7 colores y envíala al marco.</p>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {done && (
        <Alert variant="success" onClose={() => setDone('')}>
          {done}{' '}
          <Link to="/gallery" className="underline font-medium">
            Ver galería
          </Link>
        </Alert>
      )}

      {files.length === 0 && (
        <Card padding="lg">
          <label
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              accept(e.dataTransfer.files)
            }}
            className={cn(
              'flex flex-col items-center gap-4 border-2 border-dashed rounded-2xl p-12 cursor-pointer transition-colors text-center',
              dragging ? 'border-accent-500 bg-accent-50' : 'border-ink-300 hover:border-accent-500 hover:bg-accent-50',
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => accept(e.target.files)}
            />
            <div className="w-16 h-16 bg-ink-100 rounded-full flex items-center justify-center">
              <ImagePlus className="w-8 h-8 text-ink-600" />
            </div>
            <div>
              <p className="text-lg font-medium text-ink-900">Toca para elegir fotos</p>
              <p className="text-sm text-ink-500 mt-1">o arrástralas aquí · varias a la vez se recortan centradas</p>
            </div>
            <p className="text-xs text-ink-400">JPG, PNG, WebP · máx. {MAX_MB} MB</p>
          </label>
        </Card>
      )}

      {files.length === 1 && settings && (
        <CropStep
          key={files[0].name + files[0].size}
          file={files[0]}
          rotation={settings.rotation}
          onCancel={() => reset()}
          onUploaded={(next) =>
            reset(
              next
                ? `Imagen subida. Saldrá en el marco en su próxima conexión${nextWake ? ` (${nextWake})` : ''}.`
                : 'Imagen subida y añadida a la rotación.',
            )
          }
          upload={upload}
        />
      )}

      {files.length > 1 && (
        <BulkStep files={files} onCancel={() => reset()} onDone={(n) => reset(`${n} imágenes subidas y añadidas a la rotación.`)} upload={upload} />
      )}

      <Card padding="md" className="bg-accent-50 border-accent-200">
        <div className="flex items-start gap-3">
          <Clock className="w-5 h-5 text-accent-600 mt-0.5 shrink-0" />
          <p className="text-sm text-accent-800">
            El marco cambia de foto cada <strong>{settings?.interval_minutes ?? 30} min</strong>
            {settings?.quiet_enabled && (
              <>
                {' '}
                (y no se actualiza de {settings.quiet_start} a {settings.quiet_end})
              </>
            )}
            . Si marcas «Mostrar a continuación», será la siguiente que muestre.
          </p>
        </div>
      </Card>
    </div>
  )
}

function CropStep({
  file,
  rotation,
  onCancel,
  onUploaded,
  upload,
}: {
  file: File
  rotation: number
  onCancel: () => void
  onUploaded: (showNext: boolean) => void
  upload: ReturnType<typeof useUpload>
}) {
  const [src] = useState(() => URL.createObjectURL(file))
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [area, setArea] = useState<Area | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [showNext, setShowNext] = useState(true)
  const [error, setError] = useState('')
  const aspect = frameAspect(rotation)
  const vertical = aspect < 1

  useEffect(() => () => URL.revokeObjectURL(src), [src])
  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview])

  const onCropComplete = useCallback((_: Area, px: Area) => setArea(px), [])

  // Vista previa automática con el recorte hecho en el navegador (rápido, ~100 KB)
  useEffect(() => {
    if (!area) return
    let cancelled = false
    const t = setTimeout(async () => {
      setPreviewing(true)
      try {
        const blob = await cropToCanvas(src, area, rotation)
        const fd = new FormData()
        fd.append('file', blob, 'preview.png')
        const png = await api<Blob>('/api/images/preview', { method: 'POST', body: fd })
        if (!cancelled) setPreview(URL.createObjectURL(png))
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      } finally {
        if (!cancelled) setPreviewing(false)
      }
    }, 500)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [area, src, rotation])

  const submit = async () => {
    if (!area) return
    setError('')
    try {
      await upload.mutateAsync({ file, crop: area, showNext })
      onUploaded(showNext)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Card padding="none" className="overflow-hidden">
      <div className="p-4 border-b border-ink-200 flex items-center justify-between bg-ink-50">
        <span className="text-sm font-medium text-ink-700 truncate">{file.name}</span>
        <button onClick={onCancel} className="p-2 hover:bg-ink-200 rounded-lg" title="Cancelar">
          <X className="w-5 h-5 text-ink-500" />
        </button>
      </div>

      <div className={cn('grid gap-4 p-4', vertical ? 'md:grid-cols-[1fr_auto]' : 'grid-cols-1')}>
        <div className={cn('relative bg-ink-900 rounded-xl overflow-hidden', vertical ? 'h-[28rem]' : 'h-80')}>
          <Cropper
            image={src}
            crop={crop}
            zoom={zoom}
            aspect={aspect}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={onCropComplete}
            showGrid
          />
        </div>
        <div className="flex flex-col items-center gap-2">
          <p className="text-xs font-medium text-ink-500 uppercase tracking-wide">Así se verá</p>
          <div
            className={cn(
              'relative rounded-lg border-[10px] border-ink-800 shadow-soft bg-ink-100 overflow-hidden',
              vertical ? 'w-[15rem] aspect-[480/800]' : 'w-full max-w-md aspect-[800/480]',
            )}
          >
            {preview && <img src={preview} alt="Vista previa" className="w-full h-full object-cover [image-rendering:pixelated]" />}
            {previewing && (
              <div className="absolute inset-0 flex items-center justify-center bg-white/40">
                <Loader2 className="w-6 h-6 animate-spin text-ink-600" />
              </div>
            )}
          </div>
          <p className="text-xs text-ink-400 text-center max-w-[15rem]">Simulación con los 7 colores del panel</p>
        </div>
      </div>

      <div className="p-4 border-t border-ink-200 space-y-4">
        {error && <Alert variant="error">{error}</Alert>}
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-ink-700 w-12">Zoom</label>
          <input
            type="range"
            min={1}
            max={4}
            step={0.05}
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
            className="flex-1 accent-accent-500"
          />
          <button
            className="p-2 rounded-lg hover:bg-ink-100 text-ink-500"
            title="Restablecer"
            onClick={() => {
              setZoom(1)
              setCrop({ x: 0, y: 0 })
            }}
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
        <label className="flex items-center gap-3 text-sm text-ink-700 cursor-pointer">
          <input
            type="checkbox"
            checked={showNext}
            onChange={(e) => setShowNext(e.target.checked)}
            className="w-5 h-5 rounded accent-accent-500"
          />
          Mostrar a continuación (en la próxima conexión del marco)
        </label>
        <div className="flex gap-3">
          <Button variant="outline" onClick={onCancel} className="flex-1">
            Cancelar
          </Button>
          <Button onClick={submit} isLoading={upload.isPending} disabled={!area} className="flex-1">
            <Upload className="w-4 h-4 mr-2" /> Subir
          </Button>
        </div>
      </div>
    </Card>
  )
}

function BulkStep({
  files,
  onCancel,
  onDone,
  upload,
}: {
  files: File[]
  onCancel: () => void
  onDone: (n: number) => void
  upload: ReturnType<typeof useUpload>
}) {
  const [status, setStatus] = useState<Record<number, 'pending' | 'ok' | 'error'>>({})
  const [running, setRunning] = useState(false)

  const start = async () => {
    setRunning(true)
    let ok = 0
    for (let i = 0; i < files.length; i++) {
      try {
        await upload.mutateAsync({ file: files[i] })
        ok++
        setStatus((s) => ({ ...s, [i]: 'ok' }))
      } catch {
        setStatus((s) => ({ ...s, [i]: 'error' }))
      }
    }
    setRunning(false)
    if (ok === files.length) onDone(ok)
  }

  return (
    <Card>
      <Card.Header title={`${files.length} imágenes`} subtitle="Se recortarán automáticamente por el centro" />
      <ul className="divide-y divide-ink-100 max-h-80 overflow-auto">
        {files.map((f, i) => (
          <li key={i} className="flex items-center justify-between py-2 text-sm">
            <span className="truncate text-ink-700">{f.name}</span>
            {status[i] === 'ok' && <Check className="w-4 h-4 text-success" />}
            {status[i] === 'error' && <X className="w-4 h-4 text-error" />}
          </li>
        ))}
      </ul>
      <Card.Footer>
        <Button variant="outline" onClick={onCancel} disabled={running}>
          Cancelar
        </Button>
        <Button onClick={start} isLoading={running}>
          <Upload className="w-4 h-4 mr-2" /> Subir todas
        </Button>
      </Card.Footer>
    </Card>
  )
}
