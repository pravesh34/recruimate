import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Brain,
  ChevronDown,
  FileSearch,
  Lightbulb,
  Loader2,
  MessageSquare,
  Mic,
  RefreshCw,
  Sparkles,
  Target,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import PoolJobPicker from '../components/PoolJobPicker'
import { QUESTION_TYPE_META, classNames, fmtDate } from '../services/utils'
import { Badge, EmptyState, ErrorBanner, LoadingBlock, SectionHeading } from '../components/ui'

const FILTERS = [
  ['all', 'All questions'],
  ['technical', 'Technical'],
  ['project', 'Project'],
  ['hr', 'HR'],
  ['behavioural', 'Behavioural'],
  ['problem_solving', 'Problem solving'],
]

export default function InterviewPrep() {
  const navigate = useNavigate()
  const [analyses, setAnalyses] = useState([])
  const [compatibilityId, setCompatibilityId] = useState('')
  const [bank, setBank] = useState(null)
  const [filter, setFilter] = useState('all')
  const [openIndex, setOpenIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [poolBusy, setPoolBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .listCompatibility()
      .then((rows) => {
        setAnalyses(rows)
        if (rows.length) {
          setCompatibilityId(String(rows[0].id))
          return generate(rows[0].id)
        }
      })
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function generate(id) {
    if (!id) return
    setGenerating(true)
    setError('')
    try {
      const data = await api.interviewPrep({ compatibility_id: Number(id), limit: 16 })
      setBank(data)
      setOpenIndex(0)
      if (data.warning) setError(data.warning)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setGenerating(false)
    }
  }

  async function generateFromPool(job) {
    setPoolBusy(true)
    setError('')
    try {
      const analysis = await api.analyzeCompatibility({ pool_job_id: job.id })
      const rows = await api.listCompatibility()
      setAnalyses(rows)
      setCompatibilityId(String(analysis.id))
      await generate(analysis.id)
    } finally {
      setPoolBusy(false)
    }
  }

  const filtered = useMemo(() => {
    const questions = bank?.questions || []
    return filter === 'all' ? questions : questions.filter((q) => q.type === filter)
  }, [bank, filter])

  const counts = useMemo(() => {
    const result = { all: bank?.questions?.length || 0 }
    for (const question of bank?.questions || []) {
      result[question.type] = (result[question.type] || 0) + 1
    }
    return result
  }, [bank])

  if (loading) return <LoadingBlock label="Building your question bank…" />

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      <div className="card card-pad">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="section-title">Question bank</h3>
            <p className="mt-0.5 max-w-2xl text-xs leading-relaxed text-ink-500">
              Generated from the role requirements, your matched skills, your missing skills and your actual
              projects. Expected points help you structure practice — they are not scripts.
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            {analyses.length > 0 && (
              <div>
                <label className="label">Target role</label>
                <select
                  className="input min-w-[240px] py-2 text-xs"
                  value={compatibilityId}
                  onChange={(e) => {
                    setCompatibilityId(e.target.value)
                    generate(e.target.value)
                  }}
                >
                  {analyses.map((analysis) => (
                    <option key={analysis.id} value={analysis.id}>
                      {analysis.job_title || 'Role'} — {Math.round(analysis.overall_score)}/100
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button className="btn-secondary" onClick={() => generate(compatibilityId)} disabled={generating || !compatibilityId}>
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Regenerate
            </button>
            <Link
              to="/mock-interview"
              state={{ compatibilityId: Number(compatibilityId) || undefined }}
              className={classNames('btn-primary', !compatibilityId && 'pointer-events-none opacity-50')}
            >
              <Mic className="h-4 w-4" /> Start mock
            </Link>
          </div>
        </div>
      </div>

      <PoolJobPicker
        icon={Brain}
        title="Prep for a job from my pool"
        description="Pick one of your saved jobs — RecruiMate scores it against your resume and builds the question bank from it."
        actionLabel="Build question bank"
        onPick={generateFromPool}
        busy={poolBusy}
      />

      {!analyses.length ? (
        <EmptyState
          icon={FileSearch}
          title="Analyse a job first"
          description="Questions are tailored to a specific role. Run a compatibility analysis, then come back for your bank."
          action={<Link to="/compatibility" className="btn-primary">Analyse a job</Link>}
        />
      ) : generating && !bank ? (
        <LoadingBlock label="Generating role-specific questions…" />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="scroll-thin flex gap-1 overflow-x-auto rounded-xl bg-ink-100 p-1">
              {FILTERS.map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setFilter(value)}
                  className={classNames(
                    'flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition',
                    filter === value ? 'bg-white text-brand-700 shadow-sm' : 'text-ink-500 hover:text-ink-700',
                  )}
                >
                  {label}
                  <span className="rounded-full bg-ink-100 px-1.5 text-[10px] text-ink-500">{counts[value] || 0}</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 text-xs text-ink-500">
              <Sparkles className="h-3.5 w-3.5 text-brand-500" />
              Provider: <Badge tone="blue">{bank?.provider || 'heuristic'}</Badge>
            </div>
          </div>

          <div className="space-y-3">
            {filtered.map((question, index) => {
              const meta = QUESTION_TYPE_META[question.type] || QUESTION_TYPE_META.technical
              const open = openIndex === index
              return (
                <div key={question.id || index} className="card overflow-hidden">
                  <button
                    onClick={() => setOpenIndex(open ? -1 : index)}
                    className="flex w-full items-start gap-3 px-5 py-4 text-left"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-xs font-bold text-brand-600">
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                        <span className={meta.className}>{meta.label}</span>
                        <span className="chip">{question.difficulty}</span>
                        {question.related_skill && <span className="chip-violet">{question.related_skill}</span>}
                      </div>
                      <p className="text-sm font-medium leading-relaxed text-ink-800">{question.question}</p>
                    </div>
                    <ChevronDown className={classNames('mt-1 h-4 w-4 shrink-0 text-ink-400 transition', open && 'rotate-180')} />
                  </button>
                  {open && (
                    <div className="border-t border-ink-100 bg-ink-50/40 px-5 py-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                            <Lightbulb className="h-3.5 w-3.5 text-amber-500" /> Expected answer points
                          </p>
                          <ul className="space-y-1.5">
                            {(question.expected_points || []).map((point) => (
                              <li key={point} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-400" /> {point}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                            <MessageSquare className="h-3.5 w-3.5 text-brand-500" /> Follow-ups
                          </p>
                          <ul className="space-y-1.5">
                            {(question.follow_ups || []).map((followUp) => (
                              <li key={followUp} className="rounded-lg bg-white px-3 py-2 text-xs leading-relaxed text-ink-600">
                                {followUp}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                      {question.why_asked && (
                        <p className="mt-3 flex gap-2 rounded-lg bg-white px-3 py-2 text-[11px] leading-relaxed text-ink-500">
                          <Target className="mt-0.5 h-3 w-3 shrink-0 text-brand-400" /> {question.why_asked}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
            {filtered.length === 0 && (
              <EmptyState compact icon={Brain} title="No questions in this category" description="Try another filter or regenerate the bank." />
            )}
          </div>

          <div className="flex items-center justify-between rounded-2xl bg-gradient-to-r from-brand-950 to-brand-800 px-5 py-4 text-white">
            <div>
              <p className="text-sm font-semibold">Ready to say it out loud?</p>
              <p className="text-xs text-brand-100/70">Reading answers is not practice. Run a mock interview and get scored.</p>
            </div>
            <button
              className="btn bg-white text-brand-900 hover:bg-brand-50 btn-sm shrink-0"
              onClick={() => navigate('/mock-interview', { state: { compatibilityId: Number(compatibilityId) } })}
            >
              Practise now <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
