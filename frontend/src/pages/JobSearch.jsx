import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Briefcase, Lightbulb, Sparkles, Upload } from 'lucide-react'
import api, { apiError } from '../services/api'
import JobMatchRanking from '../components/JobMatchRanking'
import JobSearchPanel from '../components/JobSearchPanel'
import { EmptyState, ErrorBanner, LoadingBlock } from '../components/ui'

export default function JobSearch() {
  const [resume, setResume] = useState(null)
  const [resumes, setResumes] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [poolSize, setPoolSize] = useState(null)
  const [insights, setInsights] = useState(null)
  const [buildingPlan, setBuildingPlan] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.getResume().catch(() => null),
      api.listResumes().catch(() => []),
      api.listPool().catch(() => null),
    ])
      .then(([latest, list, pool]) => {
        setResume(latest)
        const items = Array.isArray(list) ? list : []
        setResumes(items)
        const id = latest?.id ?? items[0]?.id ?? null
        setSelectedId(id)
        if (pool && typeof pool.total === 'number') setPoolSize(pool.total)
      })
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }, [])

  async function refreshPool() {
    try {
      const pool = await api.listPool()
      if (pool && typeof pool.total === 'number') setPoolSize(pool.total)
    } catch {
      /* the count is cosmetic — ignore failures */
    }
  }

  useEffect(() => {
    if (!selectedId) return
    let alive = true
    api
      .poolInsights(selectedId)
      .then((d) => alive && setInsights(d))
      .catch(() => alive && setInsights(null))
    return () => {
      alive = false
    }
  }, [selectedId, poolSize])

  async function buildCombinedPlan() {
    setBuildingPlan(true)
    setError('')
    try {
      const gap = await api.generateGapForPool({ resume_id: selectedId })
      navigate(`/skill-gap?gap=${gap.id}`)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBuildingPlan(false)
    }
  }

  if (loading) return <LoadingBlock label="Loading your resume…" />

  const hasResume = Boolean(resume?.id || resume?.profile?.name || resumes.length)
  const activeResume = resumes.find((r) => r.id === selectedId) || resume

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] p-6 text-white shadow-lift sm:p-8">
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="relative max-w-2xl">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/80">
            <Sparkles className="h-3.5 w-3.5" /> Job search
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
            Your target job pool, ranked against your resume.
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-brand-100/75">
            Pull real postings from live job boards into your personal pool, then let RecruiMate score
            every one against your extracted evidence — skills, projects, education and experience.
          </p>
          {hasResume && (
            <p className="mt-3 text-xs text-brand-100/60">
              Scoring against <span className="font-semibold text-white">{activeResume?.filename || 'your latest resume'}</span>
              {typeof poolSize === 'number' && <> · {poolSize} job{poolSize === 1 ? '' : 's'} in your pool</>}
            </p>
          )}
        </div>
      </div>

      {hasResume && resumes.length > 1 && (
        <div className="card card-pad">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="section-title">Which resume should we score against?</h3>
              <p className="mt-0.5 text-xs text-ink-500">
                Switch profiles to re-rank the pool against different evidence.
              </p>
            </div>
            <select
              value={selectedId ?? ''}
              onChange={(e) => setSelectedId(Number(e.target.value))}
              className="rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm font-medium text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.filename || `Resume #${r.id}`}
                  {r.id === resume?.id ? ' (latest)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {hasResume ? (
        <JobMatchRanking resumeId={selectedId ?? resume?.id} limit={20} />
      ) : (
        <EmptyState
          icon={Upload}
          title="Upload a resume first"
          description="The ranking is driven by your extracted profile. Upload a PDF, DOCX or TXT resume and every posting gets scored against it."
          action={
            <Link to="/resume" className="btn-primary">
              <Upload className="h-4 w-4" /> Upload resume
            </Link>
          }
        />
      )}

      {insights?.jobs_scored > 0 && (
        <div className="card card-pad">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                <Lightbulb className="h-4 w-4" />
              </span>
              <div>
                <h3 className="section-title">Learn one skill, unlock more jobs</h3>
                <p className="mt-0.5 text-xs text-ink-500">
                  Gaps aggregated across all {insights.jobs_scored} pool jobs · average fit{' '}
                  {insights.average_score}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={buildCombinedPlan}
              disabled={buildingPlan}
              className="btn-primary btn-sm shrink-0"
            >
              {buildingPlan ? 'Building…' : 'Build combined plan'}
            </button>
          </div>
          <ul className="space-y-2">
            {(insights.skill_unlocks || []).slice(0, 5).map((u) => (
              <li key={u.skill} className="flex items-center justify-between gap-3 rounded-xl bg-ink-50/60 px-3 py-2">
                <div className="min-w-0">
                  <span className="text-sm font-semibold text-ink-900">{u.skill}</span>
                  {u.partial && (
                    <span className="ml-2 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">
                      partial credit
                    </span>
                  )}
                </div>
                <span className="shrink-0 text-xs font-bold text-brand-700">
                  unlocks {u.unlocks} job{u.unlocks === 1 ? '' : 's'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <JobSearchPanel onImported={refreshPool} />

      <div className="card card-pad">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ink-50 text-brand-600">
              <Briefcase className="h-4 w-4" />
            </span>
            <div>
              <h3 className="section-title">Add a job manually</h3>
              <p className="mt-0.5 text-xs text-ink-500">
                Paste any description or posting URL — it joins the pool and ranking immediately.
              </p>
            </div>
          </div>
          <Link to="/compatibility" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
            Analyse a job →
          </Link>
        </div>
        <p className="text-xs leading-relaxed text-ink-500">{resumeCountLabel(activeResume, poolSize)}</p>
      </div>
    </div>
  )
}

function resumeCountLabel(resume, poolSize) {
  if (typeof poolSize === 'number') {
    return `${poolSize} job${poolSize === 1 ? '' : 's'} in your target pool. Import more from a board or paste a description to compare wider.`
  }
  const count = resume?.total_jobs ?? resume?.job_count
  if (typeof count === 'number') {
    return `${count} job${count === 1 ? '' : 's'} in the ranking pool. Add more to compare wider.`
  }
  return 'Every posting you import or analyse stays in your pool and is re-ranked whenever you refresh.'
}
