import { cn } from '@/lib/utils'
import { AlertCircle, CheckCircle, Info, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'

interface AlertProps {
  children: ReactNode
  variant?: 'info' | 'success' | 'warning' | 'error'
  className?: string
  onClose?: () => void
}

export function Alert({
  children,
  variant = 'info',
  className,
  onClose,
}: AlertProps) {
  const variants = {
    info: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      icon: Info,
      iconColor: 'text-blue-500',
    },
    success: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-800',
      icon: CheckCircle,
      iconColor: 'text-green-500',
    },
    warning: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      text: 'text-yellow-800',
      icon: AlertCircle,
      iconColor: 'text-yellow-500',
    },
    error: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-800',
      icon: XCircle,
      iconColor: 'text-red-500',
    },
  }

  const { bg, border, text, icon: Icon, iconColor } = variants[variant]

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg border',
        bg,
        border,
        text,
        className
      )}
      role="alert"
    >
      <Icon className={cn('w-5 h-5 flex-shrink-0 mt-0.5', iconColor)} />
      <div className="flex-1 text-sm">{children}</div>
      {onClose && (
        <button
          onClick={onClose}
          className="flex-shrink-0 hover:opacity-70 transition-opacity"
        >
          <XCircle className="w-5 h-5" />
        </button>
      )}
    </div>
  )
}
