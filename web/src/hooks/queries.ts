import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  api,
  type DeviceStatus,
  type FrameSettings,
  type ImageItem,
  type Me,
  type Report,
  type ReprocessStatus,
  type SettingsMeta,
} from '@/lib/api'

export const keys = {
  me: ['me'] as const,
  images: ['images'] as const,
  device: ['device'] as const,
  reports: (hours: number) => ['reports', hours] as const,
  settings: ['settings'] as const,
  meta: ['settings-meta'] as const,
  reprocess: ['reprocess'] as const,
}

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api<Me>('/api/auth/me'), staleTime: 60_000 })

export const useImages = () =>
  useQuery({ queryKey: keys.images, queryFn: () => api<ImageItem[]>('/api/images') })

export const useDevice = () =>
  useQuery({ queryKey: keys.device, queryFn: () => api<DeviceStatus>('/api/device'), refetchInterval: 60_000 })

export const useReports = (hours: number) =>
  useQuery({ queryKey: keys.reports(hours), queryFn: () => api<Report[]>(`/api/device/reports?hours=${hours}`) })

export const useSettings = () =>
  useQuery({ queryKey: keys.settings, queryFn: () => api<FrameSettings>('/api/settings') })

export const useSettingsMeta = () =>
  useQuery({ queryKey: keys.meta, queryFn: () => api<SettingsMeta>('/api/settings/meta'), staleTime: Infinity })

export const useReprocess = (enabled: boolean) =>
  useQuery({
    queryKey: keys.reprocess,
    queryFn: () => api<ReprocessStatus>('/api/settings/reprocess'),
    refetchInterval: (q) => (q.state.data?.running ? 1000 : enabled ? 3000 : false),
  })

/** Invalida imágenes y estado del marco tras cualquier cambio */
function useInvalidate() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: keys.images })
    qc.invalidateQueries({ queryKey: keys.device })
  }
}

export function useImageActions() {
  const invalidate = useInvalidate()
  const showNext = useMutation({
    mutationFn: (id: number) => api<number[]>(`/api/images/${id}/show-next`, { method: 'POST' }),
    onSuccess: invalidate,
  })
  const unqueue = useMutation({
    mutationFn: (id: number) => api<number[]>(`/api/queue/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })
  const setEnabled = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      api<ImageItem>(`/api/images/${id}`, { method: 'PATCH', json: { enabled } }),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/api/images/${id}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  })
  return { showNext, unqueue, setEnabled, remove }
}

export function useUpload() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ file, crop, showNext }: { file: Blob; crop?: object | null; showNext?: boolean; name?: string }) => {
      const fd = new FormData()
      fd.append('file', file, (file as File).name ?? 'imagen.jpg')
      if (crop) fd.append('crop', JSON.stringify(crop))
      if (showNext) fd.append('show_next', 'true')
      return api<ImageItem>('/api/images', { method: 'POST', body: fd })
    },
    onSuccess: invalidate,
  })
}
