import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowUpRight,
  Briefcase,
  CheckCircle2,
  ClipboardList,
  Loader2,
  MapPin,
  Mic,
  RefreshCw,
  Search,
  Target,
  XCircle,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { classNames, scoreTone } from '../services/utils'
import { EmptyState, ErrorBanner } from './ui'

const VERDICT_TONES = {
  'Strong match': 'green',
  'Good match': 'green',
  'Stretch match': 'amber',
  'Low match': 'red',
  Unscored: 'ink',
}

function skillNames(items) {
  if (!Array.isArray(items)) return []
  return items
    .map((item) => (typeof item === 'string' ? item : item?.skill))
    .filter(Boolean)
}

function MatchCard({ match, resumeId }) {
  const tone = scoreTone(match.compatibility_score)
  const verdictTone = VERDICT_TONES[match.verdict] || 'ink'
  const matched = skillNames(match.matched_skills)
  const partial = skillNames(match.partial_skills)
  const missing = skillNames(match.missing_skills)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function makePlan() {
    setBusy('plan')
    setError('')
    try {
      const gap = await api.generateGapForJob({ resume_id: resumeId, job_id: match.job_id })
      navigate(`/skill-gap?gap=${gap.id}`)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusy('')
    }
  }

  async function startInterview() {
    setBusy('interview')
    setError('')
    try {
      const session = await api.createInterviewForJob({
        resume_id: resumeId,
        job_id: match.job_id,
        question_limit: 8,
      })
      navigate(`/mock-interview/${session.id}`)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusy('')
    }
  }

  return (
    <li className="border-b border-ink-100 py-4 first:pt-0 last:border-b-0 last:pb-0">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-ink-50 text-[11px] font-bold text-ink-500">
              {match.rank}
            </span>
            <p className="text-sm font-semibold text-ink-900">{match.title}</p>
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
              verdictTone === 'green'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : verdictTone === 'amber'
                  ? 'border-amber-200 bg-amber-50 text-amber-700'
                  : verdictTone === 'red'
                    ? 'border-red-200 bg-red-50 text-red-700'
                    : 'border-ink-200 bg-ink-50 text-ink-600'
            }`}>
              {match.verdict}
            </span>
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 pl-8 text-xs text-ink-500">
            <span className="font-medium text-ink-600">{match.company}</span>
            {match.location && (
              <>
                <span className="text-ink-300">·</span>
                <span className="inline-flex items-center gap-1">
                  <MapPin className="h-3 w-3" /> {match.location}
                </span>
              </>
            )}
          </p>

          {(matched.length > 0 || missing.length > 0) && (
            <div className="mt-2 flex flex-wrap gap-1.5 pl-8">
              {matched.slice(0, 5).map((skill) => (
                <span key={`m-${skill}`} className="chip">
                  <CheckCircle2 className="mr-1 inline h-3 w-3 text-emerald-500" />
                  {skill}
                </span>
              ))}
              {partial.slice(0, 3).map((skill) => (
                <span key={`p-${skill}`} className="chip-amber">
                  {skill}
                </span>
              ))}
              {missing.slice(0, 4).map((skill) => (
                <span key={`x-${skill}`} className="chip">
                  <XCircle className="mr-1 inline h-3 w-3 text-red-400" />
                  {skill}
                </span>
              ))}
              {missing.length > 4 && (
                <span className="chip">+{missing.length - 4} more</span>
              )}
            </div>
          )}

          {open && (
            <div className="mt-3 space-y-2 rounded-xl bg-ink-50 p-3 pl-8 text-xs leading-relaxed text-ink-600">
              {match.explanation && <p>{match.explanation}</p>}
              {match.strengths?.length > 0 && (
                <div>
                  <p className="font-semibold text-ink-700">Strengths</p>
                  <ul className="mt-0.5 space-y-0.5">
                    {match.strengths.map((s, i) => (
                      <li key={i}>• {s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {match.concerns?.length > 0 && (
                <div>
                  <p className="font-semibold text-ink-700">Concerns</p>
                  <ul className="mt-0.5 space-y-0.5">
                    {match.concerns.map((s, i) => (
                      <li key={i}>• {s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {match.evidence?.length > 0 && (
                <div>
                  <p className="font-semibold text-ink-700">Evidence</p>
                  <ul className="mt-0.5 space-y-0.5">
                    {match.evidence.map((s, i) => (
                      <li key={i}>• {s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <span className={`text-lg font-bold tabular-nums ${tone.text}`}>
            {Math.round(match.compatibility_score || 0)}
          </span>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="text-[11px] font-semibold text-brand-600 hover:text-brand-700"
          >
            {open ? 'Hide' : 'Why?'}
          </button>
          {match.url && (
            <a
              href={match.url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-600 hover:text-brand-700"
            >
              Apply <ArrowUpRight className="h-3 w-3" />
            </a>
          )}
          <div className="mt-1 flex flex-col items-end gap-1">
            <button
              type="button"
              onClick={makePlan}
              disabled={Boolean(busy)}
              className="btn-secondary btn-sm inline-flex items-center gap-1"
              title="Build a plan of approach for this role"
            >
              {busy === 'plan' ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <ClipboardList className="h-3 w-3" />
              )}
              Plan
            </button>
            <button
              type="button"
              onClick={startInterview}
              disabled={Boolean(busy)}
              className="btn-primary btn-sm inline-flex items-center gap-1"
              title="Practise a scored mock interview for this role"
            >
              {busy === 'interview' ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Mic className="h-3 w-3" />
              )}
              Interview
            </button>
          </div>
        </div>
      </div>
      {error && (
        <p className="mt-2 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-600">{error}</p>
      )}
    </li>
  )
}

export default function JobMatchRanking({ resumeId, limit = 8 }) {
  const [state, setState] = useState({ loading: true, error: '', matches: [], total: 0 })
  const [filter, setFilter] = useState('all')

  const load = () => {
    setState((s) => ({ ...s, loading: true, error: '' }))
    api
      .matchResumeToJobs(resumeId)
      .then((data) =>
        setState({
          loading: false,
          error: '',
          matches: data.matches || [],
          total: data.total || (data.matches || []).length,
          resumeFilename: data.resume_filename || '',
        }),
      )
      .catch((e) => setState((s) => ({ ...s, loading: false, error: apiError(e) })))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId])

  const visible = useMemo(() => {
    const list = state.matches || []
    if (filter === 'all') return list
    if (filter === 'strong') return list.filter((m) => m.compatibility_score >= 50)
    if (filter === 'stretch') return list.filter((m) => m.compatibility_score >= 30 && m.compatibility_score < 50)
    return list.filter((m) => m.compatibility_score < 30)
  }, [state.matches, filter])

  return (
    <div className="card card-pad">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="section-title">Jobs matched to your resume</h3>
          <p className="mt-0.5 text-xs text-ink-500">
            Every posting scored against your evidence, best fit first.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={state.loading}
          className="btn-secondary btn-sm"
        >
          {state.loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Re-rank
        </button>
      </div>

      {state.error && <ErrorBanner message={state.error} onDismiss={() => setState((s) => ({ ...s, error: '' }))} />}

      {state.loading ? (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink-500">
          <Loader2 className="h-4 w-4 animate-spin text-brand-500" /> Scoring {state.total || 'all'} postings…
        </div>
      ) : (state.matches || []).length === 0 ? (
        <EmptyState
          compact
          icon={Search}
          title="No job postings to rank yet"
          description="Import or analyse a job description first, then come back to see every role ranked by compatibility."
          action={
            <Link to="/jobs" className="btn-primary btn-sm">
              Go to job hub
            </Link>
          }
        />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-1.5">
            {[
              { key: 'all', label: `All ${state.matches.length}` },
              { key: 'strong', label: 'Strong 50+' },
              { key: 'stretch', label: 'Stretch 30-49' },
              { key: 'weak', label: 'Below 30' },
            ].map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setFilter(option.key)}
                className={classNames(
                  'rounded-full border px-2.5 py-1 text-[11px] font-semibold transition',
                  filter === option.key
                    ? 'border-brand-500 bg-brand-50 text-brand-700'
                    : 'border-ink-200 bg-white text-ink-500 hover:border-ink-300',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>

          {visible.length === 0 ? (
            <p className="py-6 text-center text-sm text-ink-500">No jobs in this band.</p>
          ) : (
            <ul className="divide-y divide-ink-100">
              {visible.slice(0, limit).map((match) => (
                <MatchCard key={match.job_id} match={match} resumeId={resumeId} />
              ))}
            </ul>
          )}

          {visible.length > limit && (
            <p className="mt-3 text-center text-[11px] text-ink-400">
              Showing top {limit} of {visible.length}. Narrow the filter to see more.
            </p>
          )}
        </>
      )}
    </div>
  )
}
