import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ImagePlus, Images, LogOut, Monitor, Settings, Tablet } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { BatteryPill, FrameStatusCard } from './FrameStatus'

const nav = [
  { label: 'Subir', href: '/', icon: ImagePlus },
  { label: 'Galería', href: '/gallery', icon: Images },
  { label: 'Marco', href: '/frame', icon: Tablet },
  { label: 'Ajustes', href: '/settings', icon: Settings },
]

export function Layout() {
  const qc = useQueryClient()
  const navigate = useNavigate()

  const logout = async () => {
    await api('/api/auth/logout', { method: 'POST' })
    qc.clear()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-ink-50">
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur border-b border-ink-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <NavLink to="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 bg-ink-900 rounded-xl flex items-center justify-center group-hover:bg-accent-500 transition-colors">
              <Monitor className="w-5 h-5 text-white" />
            </div>
            <div className="hidden sm:block">
              <p className="text-lg font-semibold text-ink-900 leading-tight">E-Ink Frame</p>
              <p className="text-xs text-ink-500">Marco de fotos</p>
            </div>
          </NavLink>
          <div className="flex items-center gap-2">
            <BatteryPill />
            <button
              onClick={logout}
              className="p-2 rounded-lg text-ink-500 hover:bg-ink-100 hover:text-ink-900 transition-colors"
              title="Cerrar sesión"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto flex">
        <aside className="hidden lg:flex flex-col w-64 shrink-0 min-h-[calc(100vh-4rem)] p-4 gap-4 border-r border-ink-200 bg-white">
          <nav className="space-y-1">
            {nav.map(({ label, href, icon: Icon }) => (
              <NavLink
                key={href}
                to={href}
                end={href === '/'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 px-4 py-3 rounded-xl transition-colors font-medium',
                    isActive ? 'bg-ink-900 text-white' : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
                  )
                }
              >
                <Icon className="w-5 h-5" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto">
            <FrameStatusCard />
          </div>
        </aside>

        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 pb-24 lg:pb-8">
          <Outlet />
        </main>
      </div>

      {/* Navegación inferior en móvil */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white border-t border-ink-200 grid grid-cols-4 pb-[env(safe-area-inset-bottom)]">
        {nav.map(({ label, href, icon: Icon }) => (
          <NavLink
            key={href}
            to={href}
            end={href === '/'}
            className={({ isActive }) =>
              cn(
                'flex flex-col items-center gap-1 py-2.5 text-xs font-medium',
                isActive ? 'text-ink-900' : 'text-ink-400',
              )
            }
          >
            <Icon className="w-5 h-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
