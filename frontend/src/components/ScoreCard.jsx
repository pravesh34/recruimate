import { CheckCircle2, TrendingUp } from 'lucide-react'
import { classNames, scoreTone } from '../services/utils'
import { ProgressBar, ScoreRing } from './ui'

export default function ScoreCard({ report, verdict, score, title = 'Overall match', compact = false }) {
  const value = score ?? report?.overall_score ?? 0
  const tone = scoreTone(value)
  const label = verdict || report?.verdict || tone.label
  const categories = report?.category_scores || []

  return (
    <div className={classNames('card overflow-hidden', compact ? '' : 'card-pad')}>
      <div className="relative">
        <div className="pointer-events-none absolute -right-10 -top-16 h-40 w-40 rounded-full bg-brand-100/60 blur-2xl" />
        <div className="relative flex items-center gap-5 p-5">
          <ScoreRing score={value} size={compact ? 104 : 124} />
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">{title}</p>
            <h3 className={classNames('mt-1 text-xl font-bold tracking-tight', tone.text)}>{label}</h3>
            {report?.explanation ? (
              <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-ink-500">{report.explanation}</p>
            ) : (
              <p className="mt-1 text-xs text-ink-500">Explainable, weighted scoring from your resume evidence.</p>
            )}
          </div>
        </div>
        {categories.length > 0 && (
          <div className="space-y-2.5 border-t border-ink-100 px-5 pb-5 pt-4">
            {categories.map((category) => (
              <div key={category.name}>
                <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                  <span className="flex items-center gap-1.5 font-medium text-ink-600">
                    <CheckCircle2 className="h-3 w-3 text-brand-400" />
                    {category.name}
                  </span>
                  <span className="font-semibold tabular-nums text-ink-700">
                    {Math.round(category.score)}
                    <span className="ml-1 text-[10px] font-normal text-ink-400">
                      {Math.round(category.weight * 100)}%
                    </span>
                  </span>
                </div>
                <ProgressBar value={category.score} tone={category.score >= 65 ? 'bg-emerald-500' : category.score >= 40 ? 'bg-brand-500' : 'bg-amber-500'} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function ScoreChip({ score = 0, label = 'match' }) {
  const tone = scoreTone(score)
  return (
    <span className={classNames('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold', tone.bg, tone.text)}>
      <TrendingUp className="h-3 w-3" /> {Math.round(score)}% {label}
    </span>
  )
}
