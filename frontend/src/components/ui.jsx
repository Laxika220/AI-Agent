import { useEffect } from 'react'
import { AlertTriangle, Loader2, X } from 'lucide-react'

export function Spinner({ className = 'h-4 w-4' }) {
  return <Loader2 className={`animate-spin ${className}`} />
}

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-white">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="card flex flex-col items-center justify-center px-6 py-14 text-center">
      {Icon && (
        <div className="mb-4 rounded-xl bg-surface-overlay p-3 text-brand-400">
          <Icon className="h-6 w-6" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-400">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="flex-1">{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="text-red-300/70 hover:text-red-200" aria-label="Dismiss">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

export function Modal({ open, title, onClose, children, wide = false }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 backdrop-blur-sm sm:items-center">
      <div className={`card w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} shadow-2xl`} role="dialog" aria-modal="true">
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-4">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          <button onClick={onClose} className="btn-ghost p-1.5" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

const STATUS_STYLES = {
  ready: 'bg-emerald-500/10 text-emerald-400',
  success: 'bg-emerald-500/10 text-emerald-400',
  processing: 'bg-amber-500/10 text-amber-400',
  pending: 'bg-slate-500/10 text-slate-400',
  partial: 'bg-amber-500/10 text-amber-400',
  skipped: 'bg-slate-500/10 text-slate-400',
  failed: 'bg-red-500/10 text-red-400',
  error: 'bg-red-500/10 text-red-400',
}

export function StatusBadge({ status }) {
  const busy = status === 'processing' || status === 'pending'
  return (
    <span className={`badge ${STATUS_STYLES[status] || STATUS_STYLES.pending}`}>
      {busy && <Spinner className="h-3 w-3" />}
      {status}
    </span>
  )
}

export function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`
}

export function formatRelative(date) {
  const seconds = Math.round((Date.now() - new Date(date).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return new Date(date).toLocaleDateString()
}
