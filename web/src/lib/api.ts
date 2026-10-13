import type { components } from './api-types'

export type ImageItem = components['schemas']['ImageOut']
export type DeviceStatus = components['schemas']['DeviceStatusOut']
export type Report = components['schemas']['ReportOut']
export type FrameSettings = components['schemas']['FrameSettings']
export type SettingsMeta = components['schemas']['SettingsMeta']
export type ReprocessStatus = components['schemas']['ReprocessStatus']
export type Me = components['schemas']['MeOut']
export type BatteryInfo = components['schemas']['BatteryOut']

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg ?? ''}`)
      .join(' · ')
  }
  return 'Error inesperado'
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  const res = await fetch(path, {
    credentials: 'same-origin',
    ...rest,
    headers: json !== undefined ? { 'Content-Type': 'application/json', ...headers } : headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      message = detailToMessage((await res.json()).detail)
    } catch {
      /* respuesta sin JSON */
    }
    if (res.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event('eink:unauthorized'))
    }
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  const type = res.headers.get('content-type') ?? ''
  if (type.includes('application/json')) return (await res.json()) as T
  return (await res.blob()) as T
}

export const imageUrl = (img: Pick<ImageItem, 'id' | 'etag'>, kind: 'thumb' | 'preview' | 'original') =>
  `/api/images/${img.id}/${kind}?v=${img.etag ?? '0'}`

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Error inesperado'
}
