import { cn } from '@/lib/utils'
import type { InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  icon?: React.ComponentType<{ className?: string }>
  helperText?: string
}

export function Input({
  label,
  error,
  icon: Icon,
  helperText,
  className,
  ...props
}: InputProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-sm font-medium text-ink-700">
          {label}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400">
            <Icon className="w-5 h-5" />
          </div>
        )}
        <input
          className={cn(
            'w-full px-4 py-2.5 bg-white border border-ink-300 rounded-lg',
            'text-ink-900 placeholder:text-ink-400',
            'focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-accent-500',
            'transition-colors',
            Icon && 'pl-11',
            error && 'border-error focus:ring-error focus:border-error',
            className
          )}
          {...props}
        />
      </div>
      {helperText && !error && (
        <p className="text-xs text-ink-500">{helperText}</p>
      )}
      {error && (
        <p className="text-xs text-error">{error}</p>
      )}
    </div>
  )
}
