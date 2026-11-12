import { AlertCircle, ArrowUpRight, Loader2 } from 'lucide-react'
import { classNames, scoreTone } from '../services/utils'

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h2 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-[28px]">{title}</h2>
        {description && <p className="mt-1.5 text-sm leading-relaxed text-ink-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function ScoreRing({ score = 0, size = 128, stroke = 10, label = 'match' }) {
  const safe = Math.max(0, Math.min(100, Number(score) || 0))
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const tone = scoreTone(safe)
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e8edf7" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tone.ring}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (safe / 100) * circumference}
          style={{ transition: 'stroke-dashoffset 700ms ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={classNames('font-bold tabular-nums', size >= 120 ? 'text-3xl' : 'text-xl', tone.text)}>
          {Math.round(safe)}
        </span>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">{label}</span>
      </div>
    </div>
  )
}

export function StatCard({ icon: Icon, label, value, help, tone = 'brand', suffix }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600',
    green: 'bg-emerald-50 text-emerald-600',
    violet: 'bg-violet-50 text-violet-600',
    amber: 'bg-amber-50 text-amber-600',
    ink: 'bg-ink-100 text-ink-600',
  }
  return (
    <div className="card card-pad animate-fade-up">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-500">{label}</p>
          <p className="mt-2 flex items-baseline gap-1 text-2xl font-bold tracking-tight text-ink-900">
            {value}
            {suffix && <span className="text-sm font-medium text-ink-400">{suffix}</span>}
          </p>
          {help && <p className="mt-1 text-xs text-ink-400">{help}</p>}
        </div>
        {Icon && (
          <span className={classNames('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl', tones[tone])}>
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
    </div>
  )
}

export function ProgressBar({ value = 0, tone = 'bg-brand-500', className = '' }) {
  return (
    <div className={classNames('h-2 w-full overflow-hidden rounded-full bg-ink-100', className)}>
      <div
        className={classNames('h-full rounded-full transition-all duration-700', tone)}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  )
}

export function EmptyState({ icon: Icon, title, description, action, compact = false }) {
  return (
    <div
      className={classNames(
        'flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-200 bg-white/60 px-6 text-center',
        compact ? 'py-8' : 'py-14',
      )}
    >
      {Icon && (
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-500">
          <Icon className="h-5 w-5" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-ink-800">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm leading-relaxed text-ink-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function LoadingBlock({ label = 'Working…', compact = false }) {
  return (
    <div className={classNames('flex items-center justify-center gap-2 text-sm text-ink-500', compact ? 'py-6' : 'py-16')}>
      <Loader2 className="h-4 w-4 animate-spin text-brand-500" /> {label}
    </div>
  )
}

export function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <p className="flex-1">{message}</p>
      {onDismiss && (
        <button onClick={onDismiss} className="text-xs font-semibold text-red-600 hover:underline">
          Dismiss
        </button>
      )}
    </div>
  )
}

export function SectionHeading({ title, description, action, className = '' }) {
  return (
    <div className={classNames('mb-4 flex items-start justify-between gap-3', className)}>
      <div>
        <h3 className="section-title">{title}</h3>
        {description && <p className="mt-0.5 text-xs leading-relaxed text-ink-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function Badge({ children, tone = 'ink', className = '' }) {
  const tones = {
    ink: 'border-ink-200 bg-ink-50 text-ink-600',
    blue: 'border-brand-200 bg-brand-50 text-brand-700',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    red: 'border-red-200 bg-red-50 text-red-700',
    violet: 'border-violet-200 bg-violet-50 text-violet-700',
  }
  return (
    <span
      className={classNames(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function LinkArrow({ children, onClick, href }) {
  const content = (
    <>
      {children} <ArrowUpRight className="h-3.5 w-3.5" />
    </>
  )
  if (href) {
    return (
      <a href={href} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700">
        {content}
      </a>
    )
  }
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700">
      {content}
    </button>
  )
}
