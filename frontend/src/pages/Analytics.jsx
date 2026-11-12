import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart3,
  Briefcase,
  Clock,
  Flame,
  Mic,
  Route,
  Target,
  TrendingUp,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { fmtDate } from '../services/utils'
import { CategoryBars, ScoreTrend, WeakSkillsChart } from '../components/SkillChart'
import { EmptyState, ErrorBanner, LoadingBlock, ProgressBar, SectionHeading, StatCard } from '../components/ui'

export default function Analytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .getAnalytics()
      .then(setData)
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }, [])

  const compatibilityTrend = useMemo(
    () =>
      (data?.compatibility_history || []).map((item) => ({
        label: fmtDate(item.created_at, { year: false }),
        score: item.score,
      })),
    [data],
  )
  const interviewTrend = useMemo(
    () =>
      (data?.interview_history || []).map((item) => ({
        label: fmtDate(item.created_at, { year: false }),
        score: item.score,
      })),
    [data],
  )

  if (loading) return <LoadingBlock label="Crunching your history…" />

  const totals = data?.totals || {}
  const prep = data?.preparation || {}
  const hasData = (data?.compatibility_history?.length || 0) > 0

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      {!hasData ? (
        <EmptyState
          icon={BarChart3}
          title="Analytics start with your first analysis"
          description="Compare a resume with a job, complete a mock interview, and this page will show whether you are improving."
          action={<Link to="/compatibility" className="btn-primary">Analyse a job</Link>}
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard icon={Target} label="Average compatibility" value={totals.average_compatibility || 0} suffix="/100" help={`${totals.analyses || 0} analyses`} />
            <StatCard icon={Mic} label="Average interview" value={totals.average_interview || 0} suffix="/100" help={`${totals.interviews || 0} completed`} tone="green" />
            <StatCard icon={Clock} label="Study hours completed" value={prep.hours_completed || 0} suffix={`/ ${prep.hours_planned || 0}h`} help={`${prep.completed_tasks || 0} of ${prep.total_tasks || 0} tasks`} tone="violet" />
            <StatCard icon={Flame} label="Weak skills tracked" value={data.weak_skills?.length || 0} help="Across all analyses" tone="amber" />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <div className="card card-pad">
              <SectionHeading title="Compatibility over time" description="Are you targeting roles you are increasingly ready for?" />
              {compatibilityTrend.length > 1 ? (
                <ScoreTrend data={compatibilityTrend} />
              ) : (
                <div className="flex h-[240px] items-center justify-center text-sm text-ink-400">Analyse more jobs to see a trend.</div>
              )}
            </div>
            <div className="card card-pad">
              <SectionHeading title="Interview performance" description="Completed mock sessions only." />
              {interviewTrend.length > 1 ? (
                <ScoreTrend data={interviewTrend} />
              ) : interviewTrend.length === 1 ? (
                <div className="flex h-[240px] flex-col items-center justify-center gap-2">
                  <p className="text-3xl font-bold text-brand-600">{Math.round(interviewTrend[0].score)}</p>
                  <p className="text-sm text-ink-500">First completed interview. One more to see a trend.</p>
                  <Link to="/mock-interview" className="btn-secondary btn-sm">Practise again</Link>
                </div>
              ) : (
                <div className="flex h-[240px] flex-col items-center justify-center gap-2 text-sm text-ink-400">
                  No completed interviews yet.
                  <Link to="/mock-interview" className="btn-secondary btn-sm">Start a mock interview</Link>
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-5">
            <div className="card card-pad xl:col-span-3">
              <SectionHeading title="Most common missing skills" description="Prioritise what appears repeatedly across your target roles." />
              {data.weak_skills?.length ? (
                <WeakSkillsChart skills={data.weak_skills} />
              ) : (
                <p className="py-16 text-center text-sm text-ink-400">No missing skills recorded.</p>
              )}
            </div>
            <div className="card card-pad xl:col-span-2">
              <SectionHeading title="Category averages" description="Where your score is lost." />
              {data.category_averages?.length ? (
                <CategoryBars categories={data.category_averages.map((c) => ({ name: c.name, score: c.average }))} />
              ) : (
                <p className="py-10 text-center text-sm text-ink-400">No category data.</p>
              )}
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="card card-pad lg:col-span-2">
              <SectionHeading title="Preparation progress by roadmap" description="Completed learning tasks across all gap reports." />
              {prep.by_skill?.length ? (
                <div className="space-y-4">
                  {prep.by_skill.slice(0, 6).map((item) => (
                    <div key={item.gap_id}>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="flex items-center gap-1.5 font-medium text-ink-700">
                          <Route className="h-3.5 w-3.5 text-brand-400" /> {item.skill || 'Roadmap'}
                        </span>
                        <span className="text-ink-500">
                          {item.completed}/{item.total} · {Math.round(item.percent)}%
                        </span>
                      </div>
                      <ProgressBar value={item.percent} tone={item.percent >= 70 ? 'bg-emerald-500' : 'bg-brand-500'} />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-ink-400">Generate a roadmap to track study progress.</p>
              )}
            </div>
            <div className="card card-pad">
              <SectionHeading title="Your pattern" />
              {(() => {
                const weakest = data.category_averages?.length
                  ? [...data.category_averages].sort((a, b) => a.average - b.average)[0]
                  : null
                const topMissing = data.weak_skills?.[0]
                return (
                  <div className="space-y-3 text-sm leading-relaxed text-ink-600">
                    <div className="rounded-xl bg-amber-50 p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600">Weakest category</p>
                      <p className="mt-1 font-semibold text-ink-800">{weakest ? `${weakest.name} (${weakest.average}/100)` : 'Not enough data'}</p>
                    </div>
                    <div className="rounded-xl bg-red-50 p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-red-600">Most repeated gap</p>
                      <p className="mt-1 font-semibold text-ink-800">{topMissing ? `${topMissing.skill} (${topMissing.missing}×)` : 'No repeated gap'}</p>
                    </div>
                    <p className="text-xs leading-relaxed text-ink-500">
                      The fastest improvement usually comes from closing one repeated gap and rehearsing it in a mock
                      interview, rather than reading broadly.
                    </p>
                    <Link to="/skill-gap" className="btn-primary btn-sm">
                      <TrendingUp className="h-3.5 w-3.5" /> Open roadmap
                    </Link>
                  </div>
                )
              })()}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
