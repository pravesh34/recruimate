import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  Clock,
  Lightbulb,
  Loader2,
  Mic,
  PlayCircle,
  Plus,
  RotateCcw,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import PoolJobPicker from '../components/PoolJobPicker'
import { SCORE_DIMENSIONS, classNames, fmtDate, fmtDateTime, scoreTone } from '../services/utils'
import InterviewChat from '../components/InterviewChat'
import { CategoryRadar } from '../components/SkillChart'
import { Badge, EmptyState, ErrorBanner, LoadingBlock, ProgressBar, ScoreRing, SectionHeading, StatCard } from '../components/ui'

function StartScreen({ analyses, onStart, creating, error, selected, setSelected, limit, setLimit, sessions, onPoolPick, poolBusy }) {
  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <div className="space-y-6 xl:col-span-2">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] p-6 text-white shadow-lift sm:p-8">
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative">
            <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/80">
              <Mic className="h-3.5 w-3.5" /> Mock interview
            </p>
            <h2 className="mt-2 text-2xl font-bold tracking-tight">Practice the conversation, not just the answers.</h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-brand-100/75">
              The interviewer asks one question at a time, evaluates each answer, follows up when it matters and
              produces a final report. You can stop early at any point.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              {[
                ['One question at a time', MessageIcon],
                ['Scored on six dimensions', BarChart3],
                ['Follow-ups that probe depth', TrendingUp],
              ].map(([label, Icon]) => (
                <div key={label} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
                  <Icon className="mb-1 h-4 w-4 text-brand-300" />
                  <p className="text-[11px] leading-snug text-brand-100/80">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <PoolJobPicker
          icon={Target}
          title="Interview for a job from my pool"
          description="Pick one of your saved jobs — RecruiMate analyses it against your resume and starts the interview straight away."
          actionLabel="Start interview for this job"
          onPick={onPoolPick}
          busy={poolBusy}
        />

        {error && <ErrorBanner message={error} />}

        {!analyses.length ? (
          <EmptyState
            icon={Target}
            title="Analyse a job before your mock interview"
            description="The interviewer needs a role and your compatibility report to ask relevant questions."
            action={<Link to="/compatibility" className="btn-primary">Analyse a job</Link>}
          />
        ) : (
          <div className="card card-pad">
            <SectionHeading title="Set up your session" description="Choose the target role and how long you want to practise." />
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label">Target role</label>
                <select className="input" value={selected} onChange={(e) => setSelected(e.target.value)}>
                  {analyses.map((analysis) => (
                    <option key={analysis.id} value={analysis.id}>
                      {analysis.job_title || 'Role'} — {Math.round(analysis.overall_score)}/100
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Questions</label>
                <div className="flex gap-1 rounded-xl bg-ink-100 p-1">
                  {[4, 6, 8, 10].map((count) => (
                    <button
                      key={count}
                      onClick={() => setLimit(count)}
                      className={classNames(
                        'flex-1 rounded-lg py-2 text-xs font-semibold transition',
                        limit === count ? 'bg-white text-brand-700 shadow-sm' : 'text-ink-500',
                      )}
                    >
                      {count}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-4 rounded-xl bg-brand-50/70 px-4 py-3 text-xs leading-relaxed text-ink-600">
              <Sparkles className="mr-1 inline h-3.5 w-3.5 text-brand-500" />
              Tip: answer out loud first, then type the key points. Aim for 60–120 seconds per answer with one concrete example.
            </div>
            <button className="btn-primary mt-4" onClick={onStart} disabled={creating || !selected}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
              {creating ? 'Preparing questions…' : 'Start mock interview'}
            </button>
          </div>
        )}
      </div>

      <div className="space-y-6">
        <div className="card card-pad">
          <SectionHeading title="How scoring works" />
          <ul className="space-y-2.5">
            {[
              'Technical accuracy and conceptual depth are weighted most.',
              'Communication, problem solving and relevance are judged from content, never accent or personality.',
              'Completeness rewards concrete examples and outcomes.',
              'Scores are blended with deterministic checks so one model cannot inflate them.',
            ].map((item) => (
              <li key={item} className="flex gap-2 text-xs leading-relaxed text-ink-500">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> {item}
              </li>
            ))}
          </ul>
        </div>

        <div className="card card-pad">
          <SectionHeading title="Previous sessions" />
          {sessions?.length ? (
            <ul className="space-y-2">
              {sessions.slice(0, 6).map((session) => (
                <li key={session.id}>
                  <Link to={`/mock-interview/${session.id}`} className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-ink-50">
                    <span
                      className={classNames(
                        'flex h-8 w-8 items-center justify-center rounded-lg text-[11px] font-bold',
                        session.score >= 65 ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600',
                      )}
                    >
                      {session.score ? Math.round(session.score) : '—'}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-semibold text-ink-800">{session.role}</span>
                      <span className="text-[10px] text-ink-400">
                        {session.status === 'completed' ? 'Completed' : 'In progress'} · {fmtDate(session.created_at)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-400">Your sessions will be saved here for comparison.</p>
          )}
        </div>
      </div>
    </div>
  )
}

function MessageIcon(props) {
  return <Mic {...props} />
}

function ReportView({ session, onRestart }) {
  const report = session.report || {}
  const evaluations = session.evaluations || []
  const [open, setOpen] = useState(0)
  const dims = useMemo(() => {
    if (!evaluations.length) return []
    return SCORE_DIMENSIONS.map((dim) => {
      const values = evaluations.map((e) => Number(e.scores?.[dim.key] ?? 0))
      return { ...dim, average: values.reduce((a, b) => a + b, 0) / values.length }
    })
  }, [evaluations])
  const tone = scoreTone(report.overall_performance || 0)

  return (
    <div className="space-y-6">
      <div className="card overflow-hidden">
        <div className="relative bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] px-6 py-6 text-white">
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/70">Interview report</p>
              <h2 className="mt-1 text-2xl font-bold tracking-tight">{session.role}</h2>
              <p className="mt-1 text-sm text-brand-100/70">
                {report.answered_questions || evaluations.length} answers evaluated · {fmtDateTime(session.created_at)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="chip border-white/15 bg-white/10 text-white">
                  <Sparkles className="h-3 w-3" /> {report.readiness || 'Assessed'}
                </span>
                <span className="chip border-white/15 bg-white/10 text-white">
                  <Mic className="h-3 w-3" /> {session.provider || 'heuristic'}
                </span>
              </div>
            </div>
            <ScoreRing score={report.overall_performance || 0} size={130} label="overall" />
          </div>
        </div>
        <div className="flex flex-col gap-3 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-2xl text-sm leading-relaxed text-ink-600">{report.summary}</p>
          <div className="flex shrink-0 gap-2">
            <button className="btn-secondary btn-sm" onClick={onRestart}>
              <RotateCcw className="h-3.5 w-3.5" /> New session
            </button>
            <Link to="/analytics" className="btn-primary btn-sm">
              <BarChart3 className="h-3.5 w-3.5" /> Analytics
            </Link>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={Target} label="Overall" value={Math.round(report.overall_performance || 0)} suffix="/100" tone="brand" />
        <StatCard icon={CheckCircle2} label="Questions answered" value={report.answered_questions || evaluations.length} tone="green" />
        <StatCard
          icon={TrendingUp}
          label="Strongest dimension"
          value={dims.length ? dims.reduce((a, b) => (a.average > b.average ? a : b)).label : '—'}
          tone="violet"
        />
        <StatCard
          icon={Lightbulb}
          label="Focus next"
          value={dims.length ? dims.reduce((a, b) => (a.average < b.average ? a : b)).label : '—'}
          tone="amber"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card card-pad">
          <SectionHeading title="Dimension profile" description="Average across every evaluated answer." />
          {evaluations.length ? <CategoryRadar evaluations={evaluations} /> : <p className="text-sm text-ink-500">No evaluations.</p>}
        </div>
        <div className="space-y-4">
          <div className="card card-pad">
            <SectionHeading title="Strengths" />
            <ul className="space-y-2">
              {(report.strengths || []).map((item, i) => (
                <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="card card-pad">
            <SectionHeading title="Improvement areas" />
            <ul className="space-y-2">
              {(report.improvement_areas || []).map((item, i) => (
                <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                  <Target className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="card card-pad bg-gradient-to-br from-brand-50 to-violet-50/60">
            <SectionHeading title="Recommendations" />
            <ul className="space-y-2">
              {(report.recommendations || []).map((item, i) => (
                <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-700">
                  <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div>
        <SectionHeading title="Answer-by-answer review" description="Expand each question to see scores and feedback." />
        <div className="space-y-3">
          {evaluations.map((evaluation, index) => {
            const openQuestion = open === index
            const average = evaluation.scores?.overall ?? 0
            return (
              <div key={evaluation.id} className="card overflow-hidden">
                <button className="flex w-full items-start gap-3 px-5 py-4 text-left" onClick={() => setOpen(openQuestion ? -1 : index)}>
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-xs font-bold text-brand-600">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium leading-relaxed text-ink-800">{evaluation.question}</p>
                    <p className="mt-1 text-[11px] text-ink-400">Overall {Math.round(average)}/100</p>
                  </div>
                  <ChevronDown className={classNames('mt-1 h-4 w-4 shrink-0 text-ink-400 transition', openQuestion && 'rotate-180')} />
                </button>
                {openQuestion && (
                  <div className="border-t border-ink-100 bg-ink-50/40 px-5 py-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Your answer</p>
                        <p className="rounded-xl bg-white p-3 text-xs leading-relaxed text-ink-600">{evaluation.answer}</p>
                      </div>
                      <div>
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-400">Feedback</p>
                        <p className="rounded-xl bg-white p-3 text-xs leading-relaxed text-ink-600">{evaluation.feedback}</p>
                        <div className="mt-2 grid grid-cols-3 gap-2">
                          {SCORE_DIMENSIONS.map((dim) => (
                            <div key={dim.key} className="rounded-lg bg-white px-2 py-1.5">
                              <p className="text-[9px] text-ink-400">{dim.label}</p>
                              <p className="text-xs font-semibold text-ink-700">{Math.round(evaluation.scores?.[dim.key] || 0)}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    {evaluation.suggestions?.length > 0 && (
                      <ul className="mt-3 space-y-1">
                        {evaluation.suggestions.map((suggestion, i) => (
                          <li key={i} className="text-[11px] leading-relaxed text-ink-500">• {suggestion}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function MockInterview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [analyses, setAnalyses] = useState([])
  const [sessions, setSessions] = useState([])
  const [session, setSession] = useState(null)
  const [evaluation, setEvaluation] = useState(null)
  const [selected, setSelected] = useState(String(location.state?.compatibilityId || ''))
  const [limit, setLimit] = useState(6)
  const [loading, setLoading] = useState(Boolean(id))
  const [creating, setCreating] = useState(false)
  const [poolBusy, setPoolBusy] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.allSettled([api.listCompatibility(), api.listInterviews()]).then(([compRes, sessionRes]) => {
      if (compRes.status === 'fulfilled') {
        setAnalyses(compRes.value)
        if (!selected && compRes.value.length) setSelected(String(compRes.value[0].id))
      }
      if (sessionRes.status === 'fulfilled') setSessions(sessionRes.value)
      if (!id) setLoading(false)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!id) {
      setSession(null)
      setLoading(false)
      return
    }
    setLoading(true)
    api
      .getInterview(id)
      .then((data) => {
        setSession(data)
        setEvaluation(data.evaluations?.at(-1) || null)
      })
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }, [id])

  async function start() {
    setCreating(true)
    setError('')
    try {
      const data = await api.createInterview({
        compatibility_id: Number(selected),
        question_limit: limit,
      })
      setSession(data)
      setEvaluation(null)
      navigate(`/mock-interview/${data.id}`, { replace: true })
      api.listInterviews().then(setSessions).catch(() => {})
    } catch (e) {
      setError(apiError(e))
    } finally {
      setCreating(false)
    }
  }

  async function startFromPool(job) {
    setPoolBusy(true)
    setError('')
    try {
      // Analyse the pool job first (mirrors it into job_analyses), then start
      // the interview on the fresh compatibility report.
      const analysis = await api.analyzeCompatibility({ pool_job_id: job.id })
      api
        .listCompatibility()
        .then((rows) => setAnalyses(rows))
        .catch(() => {})
      const data = await api.createInterview({
        compatibility_id: analysis.id,
        question_limit: limit,
      })
      setSession(data)
      setEvaluation(null)
      navigate(`/mock-interview/${data.id}`, { replace: true })
      api.listInterviews().then(setSessions).catch(() => {})
    } catch (e) {
      setError(apiError(e))
    } finally {
      setPoolBusy(false)
    }
  }

  async function answer(text) {
    if (!session) return
    setBusy(true)
    setError('')
    try {
      const data = await api.answerInterview(session.id, text)
      setSession(data.session)
      setEvaluation(data.evaluation)
      if (data.completed) {
        api.listInterviews().then(setSessions).catch(() => {})
      }
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusy(false)
    }
  }

  async function finishEarly() {
    if (!session) return
    if (!window.confirm('Finish this interview now and generate a report from the answers so far?')) return
    setBusy(true)
    try {
      const data = await api.completeInterview(session.id)
      setSession(data)
      api.listInterviews().then(setSessions).catch(() => {})
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingBlock label="Loading interview…" />

  if (session?.status === 'completed') {
    return (
      <div className="space-y-6">
        <ErrorBanner message={error} onDismiss={() => setError('')} />
        <ReportView session={session} onRestart={() => navigate('/mock-interview')} />
      </div>
    )
  }

  if (session?.status === 'active') {
    return (
      <div className="space-y-4">
        <ErrorBanner message={error} onDismiss={() => setError('')} />
        <div className="grid gap-6 xl:grid-cols-4">
          <div className="card overflow-hidden xl:col-span-3">
            <InterviewChat session={session} onAnswer={answer} busy={busy} evaluation={evaluation} />
          </div>
          <div className="space-y-4">
            <div className="card card-pad">
              <SectionHeading title="Session" />
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-ink-500">Progress</span>
                  <span className="font-semibold text-ink-800">{Math.round(session.progress?.percent || 0)}%</span>
                </div>
                <ProgressBar value={session.progress?.percent || 0} />
                <div className="flex items-center justify-between">
                  <span className="text-ink-500">Answered</span>
                  <span className="font-semibold text-ink-800">
                    {session.progress?.answered || 0} / {session.progress?.total || 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-ink-500">Provider</span>
                  <Badge tone="blue">{session.provider || 'heuristic'}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-ink-500">Started</span>
                  <span className="text-ink-700">{fmtDateTime(session.created_at)}</span>
                </div>
              </div>
            </div>
            <div className="card card-pad">
              <p className="text-xs font-semibold text-ink-800">Interview tips</p>
              <ul className="mt-2 space-y-2">
                {[
                  'Clarify the question if it is ambiguous.',
                  'Use one concrete example, then explain the trade-off.',
                  'State assumptions instead of guessing silently.',
                  'End with the result or what you learned.',
                ].map((tip) => (
                  <li key={tip} className="flex gap-2 text-[11px] leading-relaxed text-ink-500">
                    <Clock className="mt-0.5 h-3 w-3 shrink-0 text-brand-400" /> {tip}
                  </li>
                ))}
              </ul>
            </div>
            <button className="btn-secondary w-full" onClick={finishEarly} disabled={busy}>
              Finish & generate report
            </button>
            <Link to="/interview-prep" className="btn-ghost w-full text-xs">
              Back to question bank <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <StartScreen
      analyses={analyses}
      onStart={start}
      creating={creating}
      error={error}
      selected={selected}
      setSelected={setSelected}
      limit={limit}
      setLimit={setLimit}
      sessions={sessions}
      onPoolPick={startFromPool}
      poolBusy={poolBusy}
    />
  )
}
