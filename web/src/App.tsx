import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Layout } from '@/components/layout/Layout'
import { keys, useMe } from '@/hooks/queries'
import { FramePage } from '@/pages/Frame'
import { GalleryPage } from '@/pages/Gallery'
import { LoginPage } from '@/pages/Login'
import { NotFound } from '@/pages/NotFound'
import { SettingsPage } from '@/pages/Settings'
import { UploadPage } from '@/pages/Upload'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data, isLoading } = useMe()
  const location = useLocation()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ink-50">
        <div className="w-10 h-10 border-4 border-accent-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (!data?.authenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

export default function App() {
  const qc = useQueryClient()
  const navigate = useNavigate()

  // Si la sesión caduca, cualquier 401 lleva al login
  useEffect(() => {
    const onUnauthorized = () => {
      qc.setQueryData(keys.me, { authenticated: false, version: '' })
      navigate('/login', { replace: true })
    }
    window.addEventListener('eink:unauthorized', onUnauthorized)
    return () => window.removeEventListener('eink:unauthorized', onUnauthorized)
  }, [qc, navigate])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<UploadPage />} />
        <Route path="gallery" element={<GalleryPage />} />
        <Route path="frame" element={<FramePage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
