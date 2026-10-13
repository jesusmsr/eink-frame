import { Link } from 'react-router-dom'
import { AlertCircle, Home } from 'lucide-react'
import { Button, Card } from '@/components/ui'

export function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-50 p-4">
      <Card padding="lg" className="max-w-md w-full text-center">
        <div className="w-20 h-20 bg-ink-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <AlertCircle className="w-10 h-10 text-ink-400" />
        </div>
        <h1 className="text-6xl font-bold text-ink-900 mb-2">404</h1>
        <p className="text-ink-500 mb-8">Esta página no existe.</p>
        <Link to="/">
          <Button size="lg" className="w-full">
            <Home className="w-5 h-5 mr-2" /> Volver al inicio
          </Button>
        </Link>
      </Card>
    </div>
  )
}
