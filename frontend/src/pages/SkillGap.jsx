import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Compass,
  FlaskConical,
  ListChecks,
  Loader2,
  Route,
  Sparkles,
  Target,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import PoolJobPicker from '../components/PoolJobPicker'
import { classNames, fmtDate } from '../services/utils'
import { EmptyState, ErrorBanner, LoadingBlock, ProgressBar, SectionHeading } from '../components/ui'

export default function SkillGap() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const gapId = params.get('gap')
  const [gap, setGap] = useState(null)
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyTask, setBusyTask] = useState(null)
  const [buildingRoadmap, setBuildingRoadmap] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const gaps = await api.listGaps()
        if (cancelled) return
        setOptions(gaps)
        const id = gapId || gaps[0]?.id
        if (id) {
          const data = await api.getGap(id)
          if (!cancelled) setGap(data)
        } else {
          setGap(null)
        }
      } catch (e) {
        if (!cancelled) setError(apiError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [gapId])

  async function switchGap(id) {
    setLoading(true)
    setError('')
    try {
      setGap(await api.getGap(Number(id)))
    } catch (e) {
      setError(apiError(e))
    } finally {
      setLoading(false)
    }
  }

  async function toggleTask(task) {
    setBusyTask(task.id)
    try {
      const updated = await api.updateTask(task.id, !task.completed)
      setGap(updated)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusyTask(null)
    }
  }

  async function createRoadmap(job) {
    setBuildingRoadmap(true)
    setError('')
    try {
      const created = await api.generateGapForJob({ job_id: job.id })
      setGap(created)
      setOptions((prev) => [created, ...prev.filter((o) => o.id !== created.id)])
      navigate(`/skill-gap?gap=${created.id}`)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBuildingRoadmap(false)
    }
  }

  if (loading) return <LoadingBlock label="Loading your roadmap…" />

  const report = gap?.report
  const progress = gap?.progress || { completed: 0, total: 0, percent: 0 }

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <PoolJobPicker
        icon={Route}
        title="Create a roadmap for a job from my pool"
        description="RecruiMate reads the job's own requirements, prioritises your missing skills and builds a personalised learning plan — no pasting needed."
        actionLabel="Create roadmap"
        onPick={createRoadmap}
        busy={buildingRoadmap}
      />

      {!gap ? (
        <EmptyState
          icon={Route}
          title="No roadmap yet"
          description="Analyse a job description first. RecruiMate prioritises the missing skills and generates a personalised plan."
          action={<Link to="/compatibility" className="btn-primary">Analyse a job</Link>}
        />
      ) : (
        <>
          <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] p-6 text-white shadow-lift sm:p-8">
            <div className="absolute inset-0 bg-grid opacity-30" />
            <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-2xl">
                <p className="eyebrow text-brand-200/70">Learning roadmap</p>
                <h2 className="mt-1 text-2xl font-bold tracking-tight">
                  {report?.priority_skills?.length
                    ? `Close ${report.priority_skills.length} priority gaps`
                    : 'Deepen your existing strengths'}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-brand-100/75">{report?.summary}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="chip border-white/15 bg-white/10 text-white">
                    <Clock className="h-3 w-3" /> {Math.round(report?.total_estimated_hours || 0)} focused hours
                  </span>
                  <span className="chip border-white/15 bg-white/10 text-white">
                    <ListChecks className="h-3 w-3" /> {progress.completed}/{progress.total} tasks
                  </span>
                  <span className="chip border-white/15 bg-white/10 text-white">
                    <Sparkles className="h-3 w-3" /> {fmtDate(gap.created_at)}
                  </span>
                </div>
              </div>
              <div className="w-full max-w-xs rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-brand-200/70">Preparation progress</span>
                  <span className="font-bold text-white">{Math.round(progress.percent)}%</span>
                </div>
                <ProgressBar value={progress.percent} tone="bg-emerald-400" className="mt-2 bg-white/15" />
                <p className="mt-3 text-[11px] leading-relaxed text-brand-100/60">
                  Mark tasks complete as you finish them. Your dashboard and analytics update automatically.
                </p>
                <Link to="/interview-prep" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-white hover:text-brand-200">
                  Practise these skills <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
          </section>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              {(report?.priority_skills || []).map((skill) => (
                <span key={skill} className="chip-amber">
                  <Target className="h-3 w-3" /> {skill}
                </span>
              ))}
            </div>
            {options.length > 1 && (
              <select className="input w-auto py-2 text-xs" value={gap.id} onChange={(e) => switchGap(e.target.value)}>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {fmtDate(option.created_at)} — {option.priority_skills?.slice(0, 2).join(', ') || 'Roadmap'}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <div className="space-y-4 xl:col-span-2">
              <SectionHeading title="Your roadmap" description="Ordered by job importance. Each step includes topics and a practice artefact." />
              <ol className="space-y-4">
                {(report?.learning_roadmap || []).map((step) => {
                  const task = gap.tasks?.find((t) => t.skill === step.skill)
                  const done = task?.completed
                  return (
                    <li key={step.order} className={classNames('card p-5 transition', done && 'bg-emerald-50/40')}>
                      <div className="flex items-start gap-4">
                        <button
                          onClick={() => task && toggleTask(task)}
                          disabled={!task || busyTask === task.id}
                          className={classNames(
                            'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold transition',
                            done
                              ? 'border-emerald-500 bg-emerald-500 text-white'
                              : 'border-ink-200 bg-white text-ink-500 hover:border-brand-400 hover:text-brand-600',
                          )}
                          aria-label={done ? 'Mark incomplete' : 'Mark complete'}
                        >
                          {busyTask === task?.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : done ? (
                            <CheckCircle2 className="h-4 w-4" />
                          ) : (
                            step.order
                          )}
                        </button>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className={classNames('text-sm font-semibold', done ? 'text-emerald-800' : 'text-ink-900')}>
                              {step.title}
                            </h3>
                            <span className={step.priority === 'high' ? 'chip-red' : 'chip-amber'}>{step.priority}</span>
                            <span className="chip">
                              <Clock className="h-3 w-3" /> {step.estimated_hours}h
                            </span>
                            <span className="chip-blue">{step.skill}</span>
                          </div>
                          <p className="mt-1.5 text-xs leading-relaxed text-ink-500">{step.description}</p>

                          <div className="mt-3 grid gap-3 md:grid-cols-2">
                            <div className="rounded-xl bg-ink-50 p-3">
                              <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-ink-500">
                                <BookOpen className="h-3 w-3" /> Study topics
                              </p>
                              <ul className="space-y-1">
                                {(step.study_topics || []).map((topic) => (
                                  <li key={topic} className="flex gap-1.5 text-[11px] leading-relaxed text-ink-600">
                                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-400" /> {topic}
                                  </li>
                                ))}
                              </ul>
                            </div>
                            <div className="rounded-xl bg-brand-50/70 p-3">
                              <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-brand-600">
                                <FlaskConical className="h-3 w-3" /> Practice project
                              </p>
                              <p className="text-[11px] leading-relaxed text-ink-600">{step.practice_project}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ol>
            </div>

            <div className="space-y-6">
              <div className="card card-pad">
                <SectionHeading title="Recommended projects" description="Build proof, not just knowledge." />
                <ul className="space-y-2.5">
                  {(report?.recommended_projects || []).map((project, i) => (
                    <li key={i} className="rounded-xl border border-ink-100 p-3 text-xs leading-relaxed text-ink-600">
                      <span className="mb-1 flex h-5 w-5 items-center justify-center rounded-md bg-violet-50 text-[10px] font-bold text-violet-600">
                        {i + 1}
                      </span>
                      {project}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="card card-pad bg-gradient-to-br from-brand-50 to-violet-50/60">
                <SectionHeading title="Preparation plan" />
                <ol className="space-y-3">
                  {(report?.preparation_plan || []).map((item, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-700">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[10px] font-bold text-brand-600 shadow-sm">
                        {i + 1}
                      </span>
                      {item}
                    </li>
                  ))}
                </ol>
              </div>

              <div className="card card-pad">
                <SectionHeading title="Study topics" />
                <div className="flex flex-wrap gap-1.5">
                  {(report?.study_topics || []).map((topic) => (
                    <span key={topic} className="chip">{topic}</span>
                  ))}
                </div>
              </div>

              <div className="card card-pad">
                <div className="flex items-start gap-3">
                  <Compass className="h-5 w-5 shrink-0 text-brand-500" />
                  <div>
                    <p className="text-sm font-semibold text-ink-800">Next best action</p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-500">
                      Finish the first roadmap step, then run a mock interview that focuses on{' '}
                      <span className="font-semibold text-ink-700">{report?.priority_skills?.[0] || 'your top gap'}</span>.
                    </p>
                    <Link to="/mock-interview" className="btn-primary btn-sm mt-3">
                      Start mock interview
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
