import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Briefcase, Globe, Search, Sparkles, Upload } from 'lucide-react'
import api, { apiError } from '../services/api'
import JobMatchRanking from '../components/JobMatchRanking'
import { EmptyState, ErrorBanner, LoadingBlock } from '../components/ui'

const SOURCES = [
  { value: 'remotive', label: 'Remotive (remote jobs)' },
  { value: 'remoteok', label: 'RemoteOK' },
]

export default function JobSearch() {
  const [resume, setResume] = useState(null)
  const [resumes, setResumes] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [source, setSource] = useState('remotive')
  const [query, setQuery] = useState('')
  const [importLimit, setImportLimit] = useState(12)
  const [importing, setImporting] = useState(false)
  const [importNote, setImportNote] = useState('')
  const [poolSize, setPoolSize] = useState(null)

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

  async function importJobs() {
    setImporting(true)
    setImportNote('')
    setError('')
    try {
      const result = await api.importJobs({ source, query, limit: importLimit })
      setPoolSize(result.pool_size)
      setImportNote(
        `Imported ${result.imported} new posting${result.imported === 1 ? '' : 's'}` +
          (result.updated ? `, refreshed ${result.updated}` : '') +
          ` from ${result.source}. Your pool now holds ${result.pool_size}.`
      )
    } catch (e) {
      setError(apiError(e))
    } finally {
      setImporting(false)
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

      <div className="card card-pad">
        <div className="mb-3 flex items-center gap-2">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
            <Globe className="h-4 w-4" />
          </span>
          <div>
            <h3 className="section-title">Import real jobs into your pool</h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Live postings from public job boards, pulled server-side. Each candidate's pool is private.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[180px] flex-1">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
              Board
            </span>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm font-medium text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              {SOURCES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          <label className="min-w-[220px] flex-[2]">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
              Search term (optional)
            </span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. backend engineer, data analyst, fastapi"
              className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 placeholder:text-ink-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </label>

          <label className="w-24">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
              Count
            </span>
            <select
              value={importLimit}
              onChange={(e) => setImportLimit(Number(e.target.value))}
              className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm font-medium text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              {[6, 12, 20, 30].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={importJobs}
            disabled={importing}
            className="btn-primary shrink-0"
          >
            {importing ? (
              <Loader label="Importing…" />
            ) : (
              <>
                <Search className="h-4 w-4" /> Import jobs
              </>
            )}
          </button>
        </div>

        {importNote && (
          <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            {importNote}
          </p>
        )}
      </div>

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

function Loader({ label }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
      {label}
    </span>
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
