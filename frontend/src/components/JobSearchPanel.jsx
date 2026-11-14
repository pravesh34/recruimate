import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ExternalLink, Globe, Loader2, Search, ShieldCheck } from 'lucide-react'
import api, { apiError } from '../services/api'
import { classNames } from '../services/utils'

/**
 * Unified job-search panel: public boards (Remotive, RemoteOK — fetched
 * server-side) and the Jobs CLI sources (LinkedIn, Indeed, YZi Talent,
 * CivicInfo BC, TransLink) in a single form. Nothing enters the pool until
 * the candidate presses "Add" on a row.
 */

const BOARD_SOURCES = [
  { value: 'remotive', label: 'Remotive', hint: 'remote-only board' },
  { value: 'remoteok', label: 'RemoteOK', hint: 'remote-only board' },
]

const CLI_SOURCES = [
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'indeed', label: 'Indeed' },
  { value: 'yzi', label: 'YZi Talent' },
  { value: 'civicinfo', label: 'CivicInfo BC' },
  { value: 'translink', label: 'TransLink' },
]

const ALL_SOURCES = [...BOARD_SOURCES, ...CLI_SOURCES]

const SOURCE_BADGE = {
  remotive: 'bg-teal-100 text-teal-700',
  remoteok: 'bg-slate-200 text-slate-700',
  linkedin: 'bg-sky-100 text-sky-700',
  indeed: 'bg-indigo-100 text-indigo-700',
  yzi: 'bg-emerald-100 text-emerald-700',
  civicinfo: 'bg-amber-100 text-amber-700',
  translink: 'bg-violet-100 text-violet-700',
}

export default function JobSearchPanel({ onImported }) {
  const [cliStatus, setCliStatus] = useState(null)
  const [sources, setSources] = useState(['remotive', 'linkedin', 'indeed'])
  const [query, setQuery] = useState('')
  const [location, setLocation] = useState('')
  const [country, setCountry] = useState('')
  const [remote, setRemote] = useState(false)
  const [limit, setLimit] = useState(12)
  const [rows, setRows] = useState([])
  const [sourceErrors, setSourceErrors] = useState([])
  const [searching, setSearching] = useState(false)
  const [addingKey, setAddingKey] = useState('')
  const [addedKeys, setAddedKeys] = useState([])
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

  const cliAvailable = Boolean(cliStatus?.available)

  useEffect(() => {
    api.cliStatus().then(setCliStatus).catch(() => setCliStatus(null))
  }, [])

  // Show the location/country/remote fields only when a CLI source can use them.
  const cliSelected = useMemo(
    () => sources.some((s) => CLI_SOURCES.some((c) => c.value === s)),
    [sources],
  )
  const boardSelected = useMemo(
    () => sources.some((s) => BOARD_SOURCES.some((b) => b.value === s)),
    [sources],
  )

  function toggleSource(value) {
    setSources((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value],
    )
  }

  function rowKey(row) {
    return row.kind === 'board' ? `board:${row.url}` : `cli:${row.source}:${row.source_job_id}`
  }

  async function runSearch() {
    if (!sources.length) {
      setError('Pick at least one source to search.')
      return
    }
    setSearching(true)
    setError('')
    setNote('')
    setRows([])
    setAddedKeys([])
    setSourceErrors([])

    const boardSel = BOARD_SOURCES.filter((b) => sources.includes(b.value)).map((b) => b.value)
    const cliSel = CLI_SOURCES.filter((c) => sources.includes(c.value)).map((c) => c.value)
    const notes = []
    const errors = []

    const calls = []
    // Board sources: one call each (the board API is single-source).
    for (const board of boardSel) {
      calls.push(
        api
          .searchBoard({ source: board, query, limit })
          .then((result) =>
            (result.listings || []).map((listing) => ({ ...listing, kind: 'board' })),
          )
          .catch((e) => {
            errors.push({ source: board, message: apiError(e) })
            return []
          }),
      )
    }
    // CLI sources: one call carrying every selected source.
    if (cliSel.length) {
      if (cliAvailable) {
        calls.push(
          api
            .cliSearch({ query, location, country, sources: cliSel, remote, limit })
            .then((result) => {
              if (result.source_errors?.length) {
                for (const err of result.source_errors) {
                  errors.push({ source: err.source, message: err.message || err.code })
                }
              }
              return (result.listings || []).map((listing) => ({ ...listing, kind: 'cli' }))
            })
            .catch((e) => {
              errors.push({ source: 'Jobs CLI', message: apiError(e) })
              return []
            }),
        )
      } else {
        notes.push(
          `LinkedIn/Indeed/YZi skipped — ${cliStatus?.reason || 'the Jobs CLI is not available'}.`,
        )
      }
    }

    try {
      const batches = await Promise.all(calls)
      // Interleave the per-source batches so results mix instead of grouping.
      const merged = []
      for (let i = 0; ; i++) {
        let any = false
        for (const batch of batches) {
          if (batch[i]) {
            merged.push(batch[i])
            any = true
          }
        }
        if (!any) break
      }
      setRows(merged)
      setSourceErrors(errors)
      if (merged.length === 0) {
        notes.unshift('No listings matched. Try another source, term or location.')
      } else {
        notes.unshift(
          `${merged.length} listing${merged.length === 1 ? '' : 's'} found from ${
            new Set(merged.map((r) => r.source)).size
          } source${new Set(merged.map((r) => r.source)).size === 1 ? '' : 's'}. Nothing is saved until you press Add.`,
        )
      }
      setNote(notes.join(' '))
    } catch (e) {
      setError(apiError(e))
    } finally {
      setSearching(false)
    }
  }

  async function addRow(row) {
    const key = rowKey(row)
    setAddingKey(key)
    setError('')
    try {
      if (row.kind === 'board') {
        const result = await api.addListingToPool({
          title: row.title,
          company: row.company,
          location: row.location,
          url: row.url,
          source: row.source,
          tags: row.tags || [],
          description: row.snippet || '',
        })
        setPoolNote(result.pool_size)
        onImported?.(result)
      } else {
        const result = await api.cliImport([row])
        setPoolNote(result.pool_size)
        onImported?.(result)
      }
      setAddedKeys((prev) => [...prev, key])
    } catch (e) {
      setError(apiError(e))
    } finally {
      setAddingKey('')
    }
  }

  function setPoolNote(poolSize) {
    setNote(
      `Added to your pool${typeof poolSize === 'number' ? ` — ${poolSize} job${poolSize === 1 ? '' : 's'} in the pool now` : ''}.`,
    )
  }

  const hasCliFields = cliSelected && cliAvailable

  return (
    <div className="card card-pad">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
            <Globe className="h-4 w-4" />
          </span>
          <div>
            <h3 className="section-title">Search job boards — add only what you want</h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Live postings from Remotive, RemoteOK, LinkedIn, Indeed and more, fetched server-side.
              Read-only: RecruiMate never applies to a job for you.
            </p>
          </div>
        </div>
        <span
          className={classNames(
            'chip text-[11px]',
            cliAvailable
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-ink-200 bg-ink-50 text-ink-500',
          )}
        >
          <ShieldCheck className="mr-1 h-3 w-3" />
          {cliAvailable ? 'All sources ready' : 'Boards only'}
        </span>
      </div>

      {/* Source chips */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {ALL_SOURCES.map((s) => {
          const cliSource = CLI_SOURCES.some((c) => c.value === s.value)
          const disabled = cliSource && !cliAvailable
          const active = sources.includes(s.value) && !disabled
          return (
            <button
              key={s.value}
              type="button"
              title={disabled ? 'Jobs CLI not available — enable it to use this source' : s.hint}
              disabled={disabled}
              onClick={() => toggleSource(s.value)}
              className={classNames(
                'rounded-full border px-3 py-1 text-xs font-semibold transition',
                disabled && 'cursor-not-allowed border-ink-100 bg-ink-50 text-ink-300',
                active
                  ? 'border-brand-300 bg-brand-50 text-brand-700'
                  : !disabled && 'border-ink-200 bg-white text-ink-500 hover:border-ink-300',
              )}
            >
              {s.label}
            </button>
          )
        })}
      </div>

      {/* Unified search form */}
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[220px] flex-[2]">
          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            Search term (optional)
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !searching && runSearch()}
            placeholder="e.g. backend engineer, data analyst, fastapi"
            className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 placeholder:text-ink-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
          />
        </label>

        {hasCliFields && (
          <label className="min-w-[170px] flex-1">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
              Location
            </span>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Toronto, ON"
              className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 placeholder:text-ink-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </label>
        )}

        {hasCliFields && (
          <label className="w-24">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
              Country
            </span>
            <input
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase().slice(0, 2))}
              placeholder="CA"
              className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 placeholder:text-ink-300 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </label>
        )}

        {hasCliFields && (
          <label className="flex items-center gap-2 pb-2 text-xs font-medium text-ink-600">
            <input
              type="checkbox"
              checked={remote}
              onChange={(e) => setRemote(e.target.checked)}
              className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-200"
            />
            Remote only
          </label>
        )}

        <label className="w-24">
          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-500">
            Count
          </span>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
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
          onClick={runSearch}
          disabled={searching || !boardSelected && !cliSelected}
          className="btn-primary shrink-0"
        >
          {searching ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Searching…
            </>
          ) : (
            <>
              <Search className="h-4 w-4" /> Search listings
            </>
          )}
        </button>
      </div>

      {note && (
        <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{note}</p>
      )}
      {error && <p className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
      {sourceErrors.map((err) => (
        <p key={`${err.source}-${err.message}`} className="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
          {err.source}: {err.message}
        </p>
      ))}

      {rows.length > 0 && (
        <ul className="mt-4 divide-y divide-ink-100 rounded-xl border border-ink-100">
          {rows.map((row) => {
            const key = rowKey(row)
            const href = row.apply_url || row.url
            return (
              <li key={key} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink-800">
                      {href ? (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 hover:text-brand-600 hover:underline"
                        >
                          {row.title}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        row.title
                      )}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-500">
                      {[row.company, row.location].filter(Boolean).join(' · ')}
                    </p>
                    {row.snippet && (
                      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-400">
                        {row.snippet}
                      </p>
                    )}
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <span
                        className={classNames(
                          'rounded-full px-2 py-0.5 text-[10px] font-semibold',
                          SOURCE_BADGE[row.source] || 'bg-ink-100 text-ink-600',
                        )}
                      >
                        {row.source}
                      </span>
                      {(row.remote || row.kind === 'board') && (
                        <span className="chip border-emerald-200 bg-emerald-50 text-[10px] text-emerald-700">
                          Remote
                        </span>
                      )}
                      {row.employment_type && (
                        <span className="chip text-[10px]">{row.employment_type}</span>
                      )}
                      {row.experience_level && (
                        <span className="chip text-[10px]">{row.experience_level}</span>
                      )}
                      {row.salary_text && <span className="chip text-[10px]">{row.salary_text}</span>}
                      {row.posted_at && (
                        <span className="chip text-[10px]">Posted {row.posted_at}</span>
                      )}
                      {row.tags?.length > 0 && (
                        <span className="text-[10px] text-ink-400">
                          {row.tags.slice(0, 5).join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm shrink-0 bg-brand-50 text-brand-700 hover:bg-brand-100"
                    disabled={addingKey === key || addedKeys.includes(key)}
                    onClick={() => addRow(row)}
                  >
                    {addedKeys.includes(key) ? (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5" /> Added ✓
                      </>
                    ) : addingKey === key ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <>+ Add to my pool</>
                    )}
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
