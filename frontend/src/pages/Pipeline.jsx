import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowUpRight,
  CalendarClock,
  ListChecks,
  Plus,
  Trash2,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { EmptyState, ErrorBanner, LoadingBlock } from '../components/ui'

const STATUS_ORDER = ['new', 'shortlisted', 'applied', 'interview', 'offer', 'rejected', 'closed']
const STATUS_LABELS = {
  new: 'New',
  shortlisted: 'Shortlisted',
  applied: 'Applied',
  interview: 'Interview',
  offer: 'Offer',
  rejected: 'Rejected',
  closed: 'Closed',
}

function EntryCard({ entry, onPatch, onDelete, busyId }) {
  const [notes, setNotes] = useState(entry.notes || '')
  const [openNotes, setOpenNotes] = useState(false)
  const busy = busyId === entry.id

  async function patch(payload) {
    return onPatch(entry.id, payload)
  }

  const due = entry.next_action_at && new Date(entry.next_action_at) <= new Date()

  return (
    <li className={`rounded-2xl border bg-white p-3.5 shadow-soft ${busy ? 'opacity-60' : ''} ${due ? 'border-amber-300' : 'border-ink-100'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink-900">{entry.title || 'Untitled role'}</p>
          <p className="mt-0.5 truncate text-xs text-ink-500">
            {entry.company || '—'}
            {entry.source && entry.source !== 'manual' ? ` · via ${entry.source}` : ''}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {entry.url && (
            <a
              href={entry.url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-brand-600 hover:text-brand-700"
              title="Open posting"
            >
              Apply <ArrowUpRight className="h-3 w-3" />
            </a>
          )}
          <button
            type="button"
            onClick={() => onDelete(entry.id)}
            className="rounded-lg p-1.5 text-ink-300 hover:bg-red-50 hover:text-red-500"
            title="Remove from pipeline"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <select
          value={entry.status}
          onChange={(e) => patch({ status: e.target.value })}
          className="rounded-lg border border-ink-200 bg-white px-2 py-1 text-xs font-semibold text-ink-700 focus:border-brand-500 focus:outline-none"
        >
          {STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>

        <label className="inline-flex items-center gap-1 text-[11px] font-semibold text-ink-500">
          <CalendarClock className={`h-3.5 w-3.5 ${due ? 'text-amber-500' : ''}`} />
          <input
            type="date"
            value={entry.next_action_at ? entry.next_action_at.slice(0, 10) : ''}
            onChange={(e) => patch({ next_action_at: e.target.value })}
            className="rounded-lg border border-ink-200 px-2 py-1 text-xs text-ink-700 focus:border-brand-500 focus:outline-none"
          />
        </label>

        <button
          type="button"
          onClick={() => setOpenNotes((v) => !v)}
          className="text-[11px] font-semibold text-brand-600 hover:text-brand-700"
        >
          {openNotes ? 'Hide notes' : entry.notes ? 'Notes ✓' : '+ Notes'}
        </button>
      </div>

      {openNotes && (
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => notes !== entry.notes && patch({ notes })}
          rows={3}
          placeholder="Recruiter name, next step, referral info…"
          className="mt-2 w-full rounded-xl border border-ink-200 px-3 py-2 text-xs text-ink-800 focus:border-brand-500 focus:outline-none"
        />
      )}

      {due && (
        <p className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] font-medium text-amber-700">
          Follow-up due: {new Date(entry.next_action_at).toLocaleDateString()}
        </p>
      )}
    </li>
  )
}

export default function Pipeline() {
  const [state, setState] = useState({ entries: [], summary: {}, due: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.listPipeline()
      setState(data)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function patch(id, payload) {
    setBusyId(id)
    setError('')
    try {
      const updated = await api.updatePipelineEntry(id, payload)
      setState((s) => ({
        ...s,
        entries: s.entries.map((e) => (e.id === id ? updated : e)),
        summary: { ...s.summary, [updated.status]: (s.summary[updated.status] || 0) + 1 },
      }))
      load()
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusyId(0)
    }
  }

  async function remove(id) {
    if (!window.confirm('Remove this job from your pipeline?')) return
    setBusyId(id)
    try {
      await api.deletePipelineEntry(id)
      setState((s) => ({ ...s, entries: s.entries.filter((e) => e.id !== id) }))
      load()
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusyId(0)
    }
  }

  const grouped = useMemo(() => {
    const by = {}
    for (const entry of state.entries) (by[entry.status] ||= []).push(entry)
    return by
  }, [state.entries])

  const total = state.entries.length

  if (loading) return <LoadingBlock label="Loading your pipeline…" />

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] p-6 text-white shadow-lift sm:p-8">
        <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="relative">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/80">
            <ListChecks className="h-3.5 w-3.5" /> Pipeline
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
            From target job to offer.
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-brand-100/75">
            Track every job you pursue, move it through stages, keep notes and set
            follow-up dates so nothing slips.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {STATUS_ORDER.map((s) => (
              <span
                key={s}
                className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-brand-100"
              >
                {STATUS_LABELS[s]} {state.summary?.[s] || 0}
              </span>
            ))}
          </div>
        </div>
      </div>

      {state.due?.length > 0 && (
        <div className="card card-pad border-amber-200 bg-amber-50/60">
          <h3 className="flex items-center gap-2 text-sm font-bold text-amber-800">
            <CalendarClock className="h-4 w-4" /> Follow-ups due ({state.due.length})
          </h3>
          <ul className="mt-2 space-y-1">
            {state.due.map((d) => (
              <li key={d.id} className="text-xs text-amber-800">
                {d.title} {d.company ? `@ ${d.company}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {total === 0 ? (
        <EmptyState
          icon={Plus}
          title="Nothing tracked yet"
          description="Rank your pool on the Job search page and hit Track on promising jobs — or analyse a job and track it from there."
          action={
            <Link to="/jobs" className="btn-primary">
              <Plus className="h-4 w-4" /> Find target jobs
            </Link>
          }
        />
      ) : (
        <div className="space-y-6">
          {STATUS_ORDER.filter((s) => grouped[s]?.length).map((status) => (
            <section key={status}>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-bold text-ink-800">
                {STATUS_LABELS[status]}
                <span className="rounded-full bg-ink-50 px-2 py-0.5 text-[11px] font-semibold text-ink-500">
                  {grouped[status].length}
                </span>
              </h3>
              <ul className="space-y-2.5">
                {grouped[status].map((entry) => (
                  <EntryCard
                    key={entry.id}
                    entry={entry}
                    onPatch={patch}
                    onDelete={remove}
                    busyId={busyId}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
