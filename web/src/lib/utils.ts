import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('es-ES', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('es-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

const rtf = new Intl.RelativeTimeFormat('es', { numeric: 'auto' })

export function relativeTime(value: string | null | undefined, now = Date.now()): string {
  if (!value) return 'nunca'
  const diff = (new Date(value).getTime() - now) / 1000
  const abs = Math.abs(diff)
  if (abs < 45) return diff < 0 ? 'hace un momento' : 'en un momento'
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), 'hour')
  return rtf.format(Math.round(diff / 86400), 'day')
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

export function formatVolts(mv: number | null | undefined): string {
  return mv == null ? '—' : `${(mv / 1000).toFixed(2)} V`
}

export function batteryTone(percent: number | null | undefined): 'good' | 'warning' | 'critical' | 'unknown' {
  if (percent == null) return 'unknown'
  if (percent > 40) return 'good'
  if (percent > 15) return 'warning'
  return 'critical'
}

export function rssiLabel(rssi: number | null | undefined): string {
  if (rssi == null) return '—'
  if (rssi >= -60) return `Excelente (${rssi} dBm)`
  if (rssi >= -70) return `Buena (${rssi} dBm)`
  if (rssi >= -80) return `Regular (${rssi} dBm)`
  return `Débil (${rssi} dBm)`
}

/** Proporción lógica del marco según la rotación (0/2 horizontal, 1/3 vertical) */
export function frameAspect(rotation: number | undefined): number {
  return rotation === 0 || rotation === 2 ? 800 / 480 : 480 / 800
}
