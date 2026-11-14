import { useEffect, useState } from 'react'
import { Briefcase, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import api, { apiError } from '../services/api'
import { classNames } from '../services/utils'

/**
 * "Use a job from my pool" picker — the same card style as the compatibility
 * page. Shared by mock interview, interview prep and the roadmap so every
 * job-facing feature can work directly off the candidate's personal pool.
 *
 * Props:
 *  - icon:       lucide icon component for the card header
 *  - title / description: card copy
 *  - actionLabel: e.g. "Start mock interview for this job"
 *  - onPick:     async (job) => void — receives the selected pool job row
 *  - busy:       disables the action while the parent is working
 */
export default function PoolJobPicker({
  icon: Icon = Briefcase,
  title = 'Use a job from my pool',
  description = 'Pick one of your own saved jobs — no pasting required.',
  actionLabel = 'Use this job',
  onPick,
  busy = false,
}) {
  const [jobs, setJobs] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    api
      .listPool()
      .then((data) => {
        if (!alive) return
        const rows = data.jobs || []
        setJobs(rows)
        if (rows.length) setSelectedId(String(rows[0].id))
      })
      .catch((e) => alive && setError(apiError(e)))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  async function act() {
    const job = jobs.find((j) => String(j.id) === selectedId)
    if (!job || busy) return
    try {
      await onPick(job)
    } catch (e) {
      setError(apiError(e))
    }
  }

  if (loading) {
    return (
      <div className="card card-pad">
        <div className="flex items-center gap-2 text-xs text-ink-400">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading your pool…
        </div>
      </div>
    )
  }

  if (!jobs.length) {
    return (
      <div className="card card-pad">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ink-50 text-ink-400">
            <Icon className="h-4 w-4" />
          </span>
          <div>
            <h3 className="section-title">{title}</h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Your pool is empty. Add jobs from the search page first and they'll show up here.
            </p>
            <Link to="/jobs" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700">
              Browse job boards →
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card card-pad">
      <div className="mb-3 flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          <Icon className="h-4 w-4" />
        </span>
        <div>
          <h3 className="section-title">{title}</h3>
          <p className="mt-0.5 text-xs text-ink-500">{description}</p>
        </div>
      </div>

      {error && <p className="mb-3 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}

      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[260px] flex-1">
          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            Job from your pool ({jobs.length})
          </span>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm font-medium text-ink-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
          >
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title || 'Untitled role'}
                {job.company ? ` — ${job.company}` : ''}
                {job.source ? ` (${job.source})` : ''}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={act}
          disabled={busy || !selectedId}
          className="btn-primary shrink-0"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
          {busy ? 'Working…' : actionLabel}
        </button>
      </div>
    </div>
  )
}
