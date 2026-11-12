import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Briefcase,
  FileText,
  GraduationCap,
  Mic,
  Route,
  Sparkles,
  Target,
  TrendingUp,
  Upload,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { fmtDate, scoreTone } from '../services/utils'
import ScoreCard from '../components/ScoreCard'
import { ScoreTrend } from '../components/SkillChart'
import { EmptyState, ErrorBanner, LoadingBlock, ProgressBar, ScoreRing, StatCard } from '../components/ui'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getDashboard()
      .then(setData)
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingBlock label="Loading your workspace…" />
  if (error) return <ErrorBanner message={error} />
  const candidate = data?.candidate || {}
  const stats = data?.stats || {}
  const hasResume = Boolean(candidate.resume_id)
  const latest = data?.latest_analysis
  const gap = data?.skill_gap
  const trend = (data?.compatibility_history || []).map((item) => ({
    label: fmtDate(item.created_at, { year: false }),
    score: item.score,
  }))

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] p-6 text-white shadow-lift sm:p-8">
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="absolute -bottom-24 right-32 h-56 w-56 rounded-full bg-violet-500/20 blur-3xl" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-xl">
            <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/80">
              <Sparkles className="h-3.5 w-3.5" /> Your preparation cockpit
            </p>
            <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
              {hasResume ? `Welcome back, ${candidate.name?.split(' ')[0] || 'there'}.` : 'Let’s get you interview-ready.'}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-brand-100/75">
              {hasResume
                ? candidate.headline || 'Upload a job description to see how your evidence maps to the role.'
                : 'Start by uploading a resume. RecruiMate extracts your profile, finds gaps against real jobs and builds a practice plan.'}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {hasResume ? (
                <>
                  <Link to="/compatibility" className="btn bg-white text-brand-900 hover:bg-brand-50">
                    <Target className="h-4 w-4" /> Analyse a job
                  </Link>
                  <Link to="/mock-interview" className="btn border border-white/20 bg-white/10 text-white hover:bg-white/15">
                    <Mic className="h-4 w-4" /> Start mock interview
                  </Link>
                </>
              ) : (
                <Link to="/resume" className="btn bg-white text-brand-900 hover:bg-brand-50">
                  <Upload className="h-4 w-4" /> Upload your resume
                </Link>
              )}
            </div>
          </div>
          <div className="flex items-center gap-5 rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
            <ScoreRing score={stats.latest_compatibility || 0} size={112} stroke={9} label="latest" />
            <div className="space-y-2 text-xs">
              <div>
                <p className="text-brand-200/60">Target readiness</p>
                <p className="mt-0.5 text-sm font-semibold text-white">
                  {stats.latest_compatibility >= 75
                    ? 'Strong — keep rehearsing'
                    : stats.latest_compatibility >= 50
                      ? 'Within reach — close the gaps'
                      : hasResume
                        ? 'Build evidence first'
                        : 'Not assessed yet'}
                </p>
              </div>
              <div className="h-px bg-white/10" />
              <div>
                <p className="text-brand-200/60">Average across analyses</p>
                <p className="mt-0.5 text-sm font-semibold text-white">{stats.average_compatibility || 0}/100</p>
              </div>
              {latest?.job_title && (
                <>
                  <div className="h-px bg-white/10" />
                  <p className="text-brand-200/60">
                    Latest: <span className="text-white">{latest.job_title}</span>
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={FileText}
          label="Skills detected"
          value={candidate.skill_count || 0}
          help={hasResume ? `From ${candidate.resume_filename}` : 'Upload a resume to begin'}
        />
        <StatCard
          icon={Briefcase}
          label="Job analyses"
          value={stats.analysis_count || 0}
          help={`${stats.job_count || 0} descriptions parsed`}
          tone="violet"
        />
        <StatCard
          icon={Mic}
          label="Mock interviews"
          value={stats.interview_count || 0}
          help={stats.average_interview ? `Average ${stats.average_interview}/100` : 'No sessions yet'}
          tone="green"
        />
        <StatCard
          icon={Route}
          label="Roadmap progress"
          value={`${Math.round(stats.preparation_percent || 0)}%`}
          help={`${stats.tasks_completed || 0} of ${stats.tasks_total || 0} tasks complete`}
          tone="amber"
        />
      </section>

      {!hasResume ? (
        <EmptyState
          icon={FileText}
          title="Your dashboard will come alive after your first upload"
          description="Upload a PDF, DOCX or TXT resume. Your data stays local unless you explicitly configure an external LLM provider."
          action={
            <Link to="/resume" className="btn-primary">
              <Upload className="h-4 w-4" /> Upload resume
            </Link>
          }
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-5">
          <div className="space-y-6 xl:col-span-3">
            <div className="card card-pad">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h3 className="section-title">Compatibility trend</h3>
                  <p className="mt-0.5 text-xs text-ink-500">Every saved analysis, oldest to newest.</p>
                </div>
                <Link to="/analytics" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                  Full analytics →
                </Link>
              </div>
              {trend.length > 1 ? (
                <ScoreTrend data={trend} />
              ) : (
                <EmptyState
                  compact
                  icon={TrendingUp}
                  title="One analysis so far"
                  description="Analyse another job description to start seeing a trend."
                  action={
                    <Link to="/compatibility" className="btn-secondary btn-sm">
                      Analyse a job
                    </Link>
                  }
                />
              )}
            </div>

            <div className="card card-pad">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h3 className="section-title">Recent job analyses</h3>
                  <p className="mt-0.5 text-xs text-ink-500">Roles you have compared your profile against.</p>
                </div>
                <Link to="/compatibility" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                  New analysis →
                </Link>
              </div>
              {data.recent_jobs?.length ? (
                <ul className="divide-y divide-ink-100">
                  {data.recent_jobs.map((job) => (
                    <li key={job.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                        <Briefcase className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink-800">{job.title}</p>
                        <p className="truncate text-xs text-ink-500">
                          {job.company || 'Company not stated'} · {fmtDate(job.created_at)}
                        </p>
                      </div>
                      <div className="hidden flex-wrap justify-end gap-1 sm:flex">
                        {(job.required_skills || []).slice(0, 2).map((skill) => (
                          <span key={skill} className="chip">{skill}</span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="py-6 text-center text-sm text-ink-500">No job descriptions analysed yet.</p>
              )}
            </div>
          </div>

          <div className="space-y-6 xl:col-span-2">
            {latest ? (
              <ScoreCard
                report={{ category_scores: [], explanation: `Latest analysis for ${latest.job_title}.` }}
                score={latest.score}
                verdict={latest.verdict}
                title="Latest compatibility"
                compact
              />
            ) : (
              <div className="card card-pad">
                <EmptyState compact icon={Target} title="No compatibility score yet" description="Paste a job description to compare it with your resume." />
              </div>
            )}

            <div className="card card-pad">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="section-title">Skill gaps</h3>
                {gap && (
                  <Link to={`/skill-gap?gap=${gap.id}`} className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                    Roadmap →
                  </Link>
                )}
              </div>
              {gap ? (
                <>
                  <div className="flex flex-wrap gap-1.5">
                    {(gap.priority_skills || []).map((skill) => (
                      <span key={skill} className="chip-amber">{skill}</span>
                    ))}
                  </div>
                  <div className="mt-4">
                    <div className="mb-1.5 flex items-center justify-between text-xs">
                      <span className="font-medium text-ink-600">Preparation progress</span>
                      <span className="font-semibold text-ink-700">{Math.round(gap.progress_percent)}%</span>
                    </div>
                    <ProgressBar value={gap.progress_percent} tone="bg-emerald-500" />
                  </div>
                  <ul className="mt-4 space-y-2">
                    {(gap.tasks || []).slice(0, 3).map((task) => (
                      <li key={task.id} className="flex items-start gap-2 text-xs text-ink-600">
                        <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${task.completed ? 'bg-emerald-500' : 'bg-ink-300'}`} />
                        <span className={task.completed ? 'line-through text-ink-400' : ''}>{task.title}</span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="py-4 text-sm text-ink-500">Analyse a job to generate your roadmap.</p>
              )}
            </div>

            <div className="card card-pad">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="section-title">Interview performance</h3>
                <Link to="/analytics" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                  History →
                </Link>
              </div>
              {data.interview_history?.length ? (
                <div className="space-y-3">
                  {data.interview_history.slice(-4).reverse().map((session) => {
                    const tone = scoreTone(session.score)
                    return (
                      <Link key={session.id} to={`/mock-interview/${session.id}`} className="flex items-center gap-3 rounded-xl p-2 hover:bg-ink-50">
                        <span className={`flex h-9 w-9 items-center justify-center rounded-xl text-xs font-bold ${tone.bg} ${tone.text}`}>
                          {Math.round(session.score)}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-semibold text-ink-800">{session.role}</p>
                          <p className="text-[11px] text-ink-400">{fmtDate(session.created_at)}</p>
                        </div>
                        <ArrowRight className="h-3.5 w-3.5 text-ink-300" />
                      </Link>
                    )
                  })}
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3 rounded-xl bg-ink-50 p-3">
                  <p className="text-xs leading-relaxed text-ink-500">
                    No completed interviews yet. Practise your weakest area first.
                  </p>
                  <Link to="/mock-interview" className="btn-primary btn-sm shrink-0">Start</Link>
                </div>
              )}
            </div>

            {candidate.weaknesses?.length > 0 && (
              <div className="card card-pad">
                <h3 className="section-title">Resume watch-outs</h3>
                <ul className="mt-3 space-y-2">
                  {candidate.weaknesses.map((item, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                      {item}
                    </li>
                  ))}
                </ul>
                <Link to="/resume" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700">
                  Review suggestions <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center justify-center gap-2 rounded-2xl border border-ink-200/70 bg-white/60 px-4 py-3 text-center text-[11px] text-ink-400">
        <GraduationCap className="h-3.5 w-3.5" />
        RecruiMate is a preparation coach. Scores explain evidence, not your worth — and never replace a hiring decision.
      </div>
    </div>
  )
}
