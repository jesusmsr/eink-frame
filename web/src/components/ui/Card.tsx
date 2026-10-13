import { cn } from '@/lib/utils'
import type { HTMLAttributes, ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  padding?: 'none' | 'sm' | 'md' | 'lg'
  shadow?: 'none' | 'sm' | 'md' | 'soft'
}

export function Card({
  children,
  className,
  padding = 'md',
  shadow = 'sm',
  ...props
}: CardProps) {
  const paddings = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }

  const shadows = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow',
    soft: 'shadow-soft',
  }

  return (
    <div
      className={cn(
        'bg-white rounded-2xl border border-ink-200',
        paddings[padding],
        shadows[shadow],
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

Card.Header = function CardHeader({
  children,
  className,
  title,
  subtitle,
  action,
}: {
  children?: ReactNode
  className?: string
  title?: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className={cn('flex items-start justify-between mb-4', className)}>
      <div className="flex-1">
        {title && (
          <h3 className="text-lg font-semibold text-ink-900">{title}</h3>
        )}
        {subtitle && (
          <p className="text-sm text-ink-500 mt-1">{subtitle}</p>
        )}
        {children}
      </div>
      {action && <div className="ml-4">{action}</div>}
    </div>
  )
}

Card.Content = function CardContent({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={className}>{children}</div>
}

Card.Footer = function CardFooter({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-end gap-3 mt-6 pt-4 border-t border-ink-100',
        className
      )}
    >
      {children}
    </div>
  )
}
