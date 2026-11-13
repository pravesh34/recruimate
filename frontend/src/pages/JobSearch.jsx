import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Briefcase, Search, Sparkles, Upload } from 'lucide-react'
import api, { apiError } from '../services/api'
import JobMatchRanking from '../components/JobMatchRanking'
import { EmptyState, ErrorBanner, LoadingBlock } from '../components/ui'

export default function JobSearch() {
  const [resume, setResume] = useState(null)
  const [resumes, setResumes] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.getResume().catch(() => null), api.listResumes().catch(() => [])])
      .then(([latest, list]) => {
        setResume(latest)
        const items = Array.isArray(list) ? list : []
        setResumes(items)
        const id = latest?.id ?? items[0]?.id ?? null
        setSelectedId(id)
      })
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }, [])

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
            Jobs that fit your resume, ranked.
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-brand-100/75">
            RecruiMate scores every posting against your extracted evidence — skills, projects, education and
            experience — then sorts them so you shortlist the roles worth your time instead of guessing.
          </p>
          {hasResume && (
            <p className="mt-3 text-xs text-brand-100/60">
              Scoring against <span className="font-semibold text-white">{activeResume?.filename || 'your latest resume'}</span>
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

      <div className="card card-pad">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div>
            <h3 className="section-title">Add a job to the pool</h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Paste any description — it joins the ranking immediately.
            </p>
          </div>
          <Link to="/compatibility" className="text-xs font-semibold text-brand-600 hover:text-brand-700">
            Analyse a job →
          </Link>
        </div>
        <div className="flex items-center gap-3 rounded-xl bg-ink-50 p-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white text-brand-600">
            <Briefcase className="h-4 w-4" />
          </span>
          <p className="flex-1 text-xs leading-relaxed text-ink-500">
            {resumeCountLabel(activeResume)}
          </p>
          <Link to="/compatibility" className="btn-secondary btn-sm shrink-0">
            <Search className="h-3.5 w-3.5" /> Add job
          </Link>
        </div>
      </div>
    </div>
  )
}

function resumeCountLabel(resume) {
  const count = resume?.total_jobs ?? resume?.job_count
  if (typeof count === 'number') {
    return `${count} job${count === 1 ? '' : 's'} in the ranking pool. Add more to compare wider.`
  }
  return 'Every analysed job stays in the pool and is re-ranked whenever you refresh.'
}
