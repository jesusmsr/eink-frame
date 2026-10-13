import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Lock, Monitor } from 'lucide-react'
import { Alert, Button, Card, Input } from '@/components/ui'
import { keys, useMe } from '@/hooks/queries'
import { api, errorMessage, type Me } from '@/lib/api'

export function LoginPage() {
  const { data } = useMe()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (data?.authenticated) return <Navigate to={from} replace />

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const me = await api<Me>('/api/auth/login', { method: 'POST', json: { password } })
      qc.setQueryData(keys.me, me)
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-ink-100 to-ink-200 p-4">
      <div className="w-full max-w-sm animate-slide-up">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-ink-900 rounded-2xl flex items-center justify-center mb-4 shadow-glow">
            <Monitor className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-ink-900">E-Ink Frame</h1>
          <p className="text-ink-500 mt-1">Introduce la contraseña para continuar</p>
        </div>
        <Card padding="lg" shadow="soft">
          {error && (
            <Alert variant="error" className="mb-4">
              {error}
            </Alert>
          )}
          <form onSubmit={submit} className="space-y-4">
            <Input
              label="Contraseña"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              icon={Lock}
              required
              autoFocus
            />
            <Button type="submit" size="lg" isLoading={loading} className="w-full">
              Entrar
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
