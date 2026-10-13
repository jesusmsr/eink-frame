import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { Eye, EyeOff, ImageIcon, ListPlus, ListX, Monitor, RefreshCw, Trash2, X } from 'lucide-react'
import { Alert, Button, Card } from '@/components/ui'
import { useImageActions, useImages, useSettings } from '@/hooks/queries'
import { errorMessage, imageUrl, type ImageItem } from '@/lib/api'
import { cn, formatDate, relativeTime } from '@/lib/utils'

type Filter = 'all' | 'enabled' | 'disabled'

export function GalleryPage() {
  const { data: images = [], isLoading, refetch, isFetching, error } = useImages()
  const { data: settings } = useSettings()
  const actions = useImageActions()
  const [filter, setFilter] = useState<Filter>('all')
  const [open, setOpen] = useState<ImageItem | null>(null)
  const [actionError, setActionError] = useState('')
  const vertical = settings ? settings.rotation % 2 === 1 : true

  const shown = useMemo(
    () => images.filter((i) => (filter === 'all' ? true : filter === 'enabled' ? i.enabled : !i.enabled)),
    [images, filter],
  )
  const current = images.find((i) => i.is_current)

  const run = async (fn: () => Promise<unknown>) => {
    setActionError('')
    try {
      await fn()
    } catch (err) {
      setActionError(errorMessage(err))
    }
  }

  const del = (img: ImageItem) =>
    run(async () => {
      if (!window.confirm(`¿Eliminar "${img.original_name}"?`)) return
      await actions.remove.mutateAsync(img.id)
      setOpen(null)
    })

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-ink-900">Galería</h1>
          <p className="text-ink-500 mt-1">
            {images.length} imágenes · {images.filter((i) => i.enabled).length} en rotación
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-ink-100 rounded-lg p-1 text-sm">
            {(
              [
                ['all', 'Todas'],
                ['enabled', 'Activas'],
                ['disabled', 'Ocultas'],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                onClick={() => setFilter(k)}
                className={cn(
                  'px-3 py-1.5 rounded-md font-medium transition-colors',
                  filter === k ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-800',
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <Button variant="ghost" size="sm" onClick={() => refetch()} title="Actualizar">
            <RefreshCw className={cn('w-4 h-4', isFetching && 'animate-spin')} />
          </Button>
        </div>
      </div>

      {error && <Alert variant="error">{errorMessage(error)}</Alert>}
      {actionError && (
        <Alert variant="error" onClose={() => setActionError('')}>
          {actionError}
        </Alert>
      )}

      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={cn('rounded-xl bg-ink-100 animate-pulse', vertical ? 'aspect-[480/800]' : 'aspect-[800/480]')} />
          ))}
        </div>
      ) : images.length === 0 ? (
        <Card padding="lg" className="text-center py-16">
          <div className="w-16 h-16 bg-ink-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ImageIcon className="w-8 h-8 text-ink-400" />
          </div>
          <h3 className="text-lg font-medium text-ink-900">Todavía no hay imágenes</h3>
          <Link to="/" className="inline-block mt-4">
            <Button>Subir la primera</Button>
          </Link>
        </Card>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {shown.map((img) => (
            <button
              key={img.id}
              onClick={() => setOpen(img)}
              className={cn(
                'group relative rounded-xl overflow-hidden bg-ink-100 border-2 text-left focus:outline-none focus:ring-2 focus:ring-accent-500',
                img.is_current ? 'border-accent-500' : 'border-transparent',
                vertical ? 'aspect-[480/800]' : 'aspect-[800/480]',
              )}
            >
              <img
                src={imageUrl(img, 'thumb')}
                alt={img.original_name}
                loading="lazy"
                className={cn('w-full h-full object-cover', !img.enabled && 'opacity-40 grayscale')}
              />
              <div className="absolute top-2 left-2 flex flex-col gap-1 items-start">
                {img.is_current && <Badge className="bg-accent-500 text-white"><Monitor className="w-3 h-3" />En el marco</Badge>}
                {img.queued && <Badge className="bg-ink-900 text-white"><ListPlus className="w-3 h-3" />Siguiente</Badge>}
                {!img.enabled && <Badge className="bg-white/90 text-ink-600"><EyeOff className="w-3 h-3" />Oculta</Badge>}
              </div>
            </button>
          ))}
        </div>
      )}

      {current && (
        <p className="text-sm text-ink-500">
          En el marco ahora: <strong className="text-ink-700">{current.original_name}</strong>
        </p>
      )}

      {open && (
        <ImageModal
          img={images.find((i) => i.id === open.id) ?? open}
          vertical={vertical}
          onClose={() => setOpen(null)}
          onDelete={del}
          actions={actions}
          run={run}
        />
      )}
    </div>
  )
}

function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium shadow-sm', className)}>
      {children}
    </span>
  )
}

function ImageModal({
  img,
  vertical,
  onClose,
  onDelete,
  actions,
  run,
}: {
  img: ImageItem
  vertical: boolean
  onClose: () => void
  onDelete: (img: ImageItem) => void
  actions: ReturnType<typeof useImageActions>
  run: (fn: () => Promise<unknown>) => void
}) {
  const [showOriginal, setShowOriginal] = useState(false)
  return createPortal(
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 animate-fade-in" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-soft max-h-full overflow-auto w-full max-w-3xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-ink-200">
          <p className="font-medium text-ink-900 truncate">{img.original_name}</p>
          <button onClick={onClose} className="p-2 hover:bg-ink-100 rounded-lg">
            <X className="w-5 h-5 text-ink-500" />
          </button>
        </div>
        <div className={cn('p-4 grid gap-6', vertical ? 'sm:grid-cols-[auto_1fr]' : 'grid-cols-1')}>
          <div className="flex flex-col items-center gap-2">
            <div
              className={cn(
                'rounded-lg border-[10px] border-ink-800 overflow-hidden bg-ink-100',
                vertical ? 'w-[16rem] aspect-[480/800]' : 'w-full aspect-[800/480]',
              )}
            >
              <img
                src={imageUrl(img, showOriginal ? 'original' : 'preview')}
                alt={img.original_name}
                className={cn('w-full h-full', showOriginal ? 'object-contain bg-ink-900' : 'object-cover [image-rendering:pixelated]')}
              />
            </div>
            <button className="text-xs text-ink-500 underline" onClick={() => setShowOriginal((v) => !v)}>
              {showOriginal ? 'Ver como en el panel' : 'Ver original'}
            </button>
          </div>
          <div className="space-y-4 text-sm">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-ink-600">
              <dt className="text-ink-400">Subida</dt>
              <dd>{formatDate(img.created_at)}</dd>
              <dt className="text-ink-400">Última vez</dt>
              <dd>{img.last_shown_at ? relativeTime(img.last_shown_at) : 'nunca'}</dd>
              <dt className="text-ink-400">Mostrada</dt>
              <dd>{img.show_count} veces</dd>
            </dl>
            <div className="flex flex-col gap-2">
              {img.queued ? (
                <Button variant="outline" onClick={() => run(() => actions.unqueue.mutateAsync(img.id))}>
                  <ListX className="w-4 h-4 mr-2" /> Quitar de la cola
                </Button>
              ) : (
                <Button onClick={() => run(() => actions.showNext.mutateAsync(img.id))} disabled={img.is_current}>
                  <ListPlus className="w-4 h-4 mr-2" /> Mostrar a continuación
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => run(() => actions.setEnabled.mutateAsync({ id: img.id, enabled: !img.enabled }))}
              >
                {img.enabled ? <EyeOff className="w-4 h-4 mr-2" /> : <Eye className="w-4 h-4 mr-2" />}
                {img.enabled ? 'Sacar de la rotación' : 'Volver a la rotación'}
              </Button>
              <Button variant="danger" onClick={() => onDelete(img)} isLoading={actions.remove.isPending}>
                <Trash2 className="w-4 h-4 mr-2" /> Eliminar
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
