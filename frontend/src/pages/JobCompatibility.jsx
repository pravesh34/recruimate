import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Briefcase,
  CheckCircle2,
  CircleDot,
  FileSearch,
  FileText,
  Link2,
  ListChecks,
  Loader2,
  PlayCircle,
  Sparkles,
  Target,
  XCircle,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { classNames, fmtDate } from '../services/utils'
import AgentActivity from '../components/AgentActivity'
import ScoreCard from '../components/ScoreCard'
import { CategoryBars } from '../components/SkillChart'
import { Badge, EmptyState, ErrorBanner, LoadingBlock, SectionHeading } from '../components/ui'

const SAMPLE = `AI Engineer (Entry Level)
Nimbus Labs | Bengaluru | Full-time

Responsibilities
- Build retrieval-augmented generation pipelines for document understanding.
- Develop FastAPI services and React interfaces.
- Work with PostgreSQL, Docker and CI/CD.

Requirements
- Strong Python programming skills.
- Experience with FastAPI, REST APIs, React and PostgreSQL.
- Familiarity with Docker, Git and unit testing.
- 1+ years of relevant experience through internships or projects.
- Bachelor's degree in Computer Science or a related field.

Preferred
- Kubernetes, AWS, LangChain, TypeScript and vector databases.`

function SkillGroup({ title, tone, items, icon: Icon, emptyText }) {
  return (
    <div className="rounded-2xl border border-ink-100 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-ink-800">
          <Icon className={classNames('h-4 w-4', tone.icon)} /> {title}
        </h4>
        <Badge tone={tone.badge}>{items.length}</Badge>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item.skill}
            className={classNames('chip', tone.chip)}
            title={item.evidence || item.matched_with || ''}
          >
            {item.skill}
            {item.status === 'partial' && item.matched_with && (
              <span className="text-[10px] opacity-70">≈ {item.matched_with}</span>
            )}
          </span>
        ))}
        {items.length === 0 && <p className="text-xs text-ink-400">{emptyText}</p>}
      </div>
    </div>
  )
}

export default function JobCompatibility() {
  const navigate = useNavigate()
  const [resume, setResume] = useState(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState('paste')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [selectedJobId, setSelectedJobId] = useState('')
  const [jobs, setJobs] = useState([])
  const [pool, setPool] = useState([])
  const [history, setHistory] = useState([])
  const [result, setResult] = useState(null)
  const [full, setFull] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const scoreRef = useRef(null)
  const reportRef = useRef(null)

  function revealScore() {
    // Bring the score into view without yanking the page around.
    setTimeout(() => {
      scoreRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 120)
  }

  useEffect(() => {
    Promise.allSettled([api.getResume(), api.listJobs(), api.listPool(), api.listCompatibility()]).then(
      ([res, jobRes, poolRes, compRes]) => {
        if (res.status === 'fulfilled') setResume(res.value)
        if (jobRes.status === 'fulfilled') setJobs(jobRes.value)
        if (poolRes.status === 'fulfilled') setPool(poolRes.value.jobs || [])
        if (compRes.status === 'fulfilled') setHistory(compRes.value)
        setLoading(false)
      }
    )
  }, [])

  const selectedJob = useMemo(() => {
    if (String(selectedJobId).startsWith('pool-')) {
      const id = Number(String(selectedJobId).slice(5))
      return pool.find((j) => j.id === id)
    }
    return jobs.find((j) => String(j.id) === String(selectedJobId))
  }, [jobs, pool, selectedJobId])
  const report = result?.report || null
  const hasInput = Boolean(selectedJobId || (mode === 'paste' ? text.trim().length > 30 : url.trim()))

  async function analyzeFast() {
    if (!resume) {
      setError('Upload a resume before analysing a job.')
      return
    }
    if (!hasInput) {
      setError('Paste a job description, add a public URL or select a saved analysis.')
      return
    }
    setAnalyzing(true)
    setError('')
    try {
      const data = await api.analyzeCompatibility({
        resume_id: resume.id,
        ...(String(selectedJobId).startsWith('pool-')
          ? { pool_job_id: Number(String(selectedJobId).slice(5)) }
          : { job_id: selectedJobId ? Number(selectedJobId) : undefined }),
        job_description: mode === 'paste' && !selectedJobId ? text : '',
        run_gap_analysis: true,
      })
      setResult(data)
      setFull(null)
      revealScore()
      api.listCompatibility().then(setHistory).catch(() => {})
    } catch (e) {
      setError(apiError(e))
    } finally {
      setAnalyzing(false)
    }
  }

  async function runFull() {
    if (!resume) {
      setError('Upload a resume before running the analysis.')
      return
    }
    if (!hasInput) {
      setError('Paste a job description or select a saved analysis first.')
      return
    }
    setRunning(true)
    setError('')
    try {
      const data = await api.runAnalysis({
        resume_id: resume.id,
        ...(String(selectedJobId).startsWith('pool-')
          ? { pool_job_id: Number(String(selectedJobId).slice(5)) }
          : { job_id: selectedJobId ? Number(selectedJobId) : undefined }),
        job_description: mode === 'paste' && !selectedJobId ? text : '',
      })
      setResult(data)
      setFull(data)
      revealScore()
      api.listJobs().then(setJobs).catch(() => {})
      api.listCompatibility().then(setHistory).catch(() => {})
    } catch (e) {
      setError(apiError(e))
    } finally {
      setRunning(false)
    }
  }

  async function checkPoolJob(poolId) {
    const value = `pool-${poolId}`
    setSelectedJobId(value)
    setMode('saved')
    setResult(null)
    setFull(null)
    if (!resume) {
      setError('Upload a resume before checking a job.')
      return
    }
    setAnalyzing(true)
    setError('')
    try {
      const data = await api.analyzeCompatibility({
        resume_id: resume.id,
        pool_job_id: Number(poolId),
        job_description: '',
        run_gap_analysis: true,
      })
      setResult(data)
      setFull(null)
      revealScore()
      api.listCompatibility().then(setHistory).catch(() => {})
    } catch (e) {
      setError(apiError(e))
    } finally {
      setAnalyzing(false)
    }
  }

  if (loading) return <LoadingBlock label="Loading your profile…" />

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      {!resume ? (
        <EmptyState
          icon={FileText}
          title="Upload a resume first"
          description="Compatibility is computed from your actual resume evidence, so we need your profile before comparing it with a job."
          action={<Link to="/resume" className="btn-primary">Upload resume</Link>}
        />
      ) : (
        <>
          <div className="grid gap-6 xl:grid-cols-5">
            <div className="card card-pad xl:col-span-3">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h3 className="section-title">Job description</h3>
                  <p className="mt-0.5 text-xs text-ink-500">
                    Paste the posting or fetch a public URL. We extract skills and requirements, then compare them with your evidence.
                  </p>
                </div>
                <Badge tone="green">{resume.profile?.name || 'Resume ready'}</Badge>
              </div>

              <div className="mb-3 flex gap-1 rounded-xl bg-ink-100 p-1">
                {[
                  ['paste', 'Paste text', FileText],
                  ['url', 'From URL', Link2],
                  ['saved', 'Saved analysis', Briefcase],
                ].map(([value, label, Icon]) => (
                  <button
                    key={value}
                    onClick={() => {
                      setMode(value)
                      if (value !== 'saved') setSelectedJobId('')
                    }}
                    className={classNames(
                      'flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold transition',
                      mode === value ? 'bg-white text-brand-700 shadow-sm' : 'text-ink-500 hover:text-ink-700',
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" /> {label}
                  </button>
                ))}
              </div>

              {mode === 'paste' && (
                <textarea
                  className="input min-h-[220px] resize-y font-mono text-[12.5px] leading-relaxed"
                  placeholder="Paste the full job description here…"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              )}
              {mode === 'url' && (
                <div>
                  <label className="label">Public job posting URL</label>
                  <input
                    className="input"
                    placeholder="https://company.com/careers/role"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                  <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
                    Private and localhost URLs are blocked. If a site blocks fetching, paste the text instead.
                  </p>
                </div>
              )}
              {mode === 'saved' && (
                <div>
                  <label className="label">Choose a job</label>
                  <select className="input" value={selectedJobId} onChange={(e) => setSelectedJobId(e.target.value)}>
                    <option value="">Select a job…</option>
                    <optgroup label="My target pool">
                      {pool.map((job) => (
                        <option key={`pool-${job.id}`} value={`pool-${job.id}`}>
                          {job.title} {job.company ? `— ${job.company}` : ''} (pool)
                        </option>
                      ))}
                    </optgroup>
                    <optgroup label="Saved analyses">
                      {jobs.map((job) => (
                        <option key={job.id} value={job.id}>
                          {job.title} {job.company ? `— ${job.company}` : ''}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                  {pool.length === 0 && jobs.length === 0 && (
                    <p className="mt-2 text-xs text-ink-400">
                      Nothing saved yet. Search the <Link to="/jobs" className="font-semibold text-brand-600">Job search</Link> page and add jobs to your pool first.
                    </p>
                  )}
                </div>
              )}

              {mode === 'paste' && !text && (
                <button className="mt-2 text-[11px] font-semibold text-brand-600 hover:text-brand-700" onClick={() => setText(SAMPLE)}>
                  Use a sample job description
                </button>
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                <button className="btn-primary" onClick={analyzeFast} disabled={analyzing || running}>
                  {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
                  {analyzing ? 'Scoring…' : 'Analyse compatibility'}
                </button>
                <button className="btn-secondary" onClick={runFull} disabled={analyzing || running}>
                  {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {running ? 'Running agents…' : 'Run full agent workflow'}
                </button>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
                The full workflow runs resume + job intelligence, compatibility, gap analysis and interview preparation.
              </p>

              {/* The score appears right here, directly under the buttons — no scrolling. */}
              {result && (
                <div ref={scoreRef} className="mt-5 border-t border-ink-100 pt-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                        Overall match
                      </p>
                      <p
                        className={classNames(
                          'mt-1 text-4xl font-bold leading-none',
                          result.overall_score >= 75
                            ? 'text-emerald-600'
                            : result.overall_score >= 50
                              ? 'text-amber-600'
                              : 'text-rose-600',
                        )}
                      >
                        {Math.round(result.overall_score)}
                        <span className="text-base font-semibold text-ink-400"> / 100</span>
                      </p>
                      <p className="mt-1.5 text-sm font-semibold text-ink-700">{report?.verdict}</p>
                      <p className="mt-0.5 max-w-sm text-xs leading-relaxed text-ink-500">
                        {selectedJob
                          ? `${selectedJob.title}${selectedJob.company ? ` — ${selectedJob.company}` : ''}`
                          : 'Your resume against this job description'}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {result.gap_id && (
                        <Link to={`/skill-gap?gap=${result.gap_id}`} className="btn-secondary btn-sm">
                          <ListChecks className="h-3.5 w-3.5" /> Roadmap
                        </Link>
                      )}
                      <button
                        className="btn-primary btn-sm"
                        onClick={() => navigate('/mock-interview', { state: { compatibilityId: result.id } })}
                      >
                        <PlayCircle className="h-3.5 w-3.5" /> Practise
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {(report?.category_scores || []).map((category) => (
                      <div key={category.name} className="rounded-xl bg-ink-50 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-semibold text-ink-700">{category.name}</span>
                          <span className="text-[11px] font-bold text-ink-500">{category.score}%</span>
                        </div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink-200">
                          <div
                            className="h-full rounded-full bg-brand-500"
                            style={{ width: `${Math.max(0, Math.min(100, category.score))}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                    <span className="chip border-emerald-200 bg-emerald-50 text-emerald-700">
                      {report?.matched_skills?.length || 0} matched
                    </span>
                    <span className="chip border-amber-200 bg-amber-50 text-amber-700">
                      {report?.partially_matched_skills?.length || 0} partial
                    </span>
                    <span className="chip border-red-200 bg-red-50 text-red-700">
                      {report?.missing_skills?.length || 0} missing
                    </span>
                    <button
                      type="button"
                      className="text-[11px] font-semibold text-brand-600 hover:text-brand-700"
                      onClick={() => reportRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                    >
                      View full breakdown ↓
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-6 xl:col-span-2">
              {/* Quick check straight from the personal job pool */}
              {pool.length > 0 && (
                <div className="card card-pad">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                      <h3 className="section-title">Check a job from my pool</h3>
                      <p className="mt-0.5 text-xs text-ink-500">
                        Pick any job in your personal pool and score it against your resume right now.
                      </p>
                    </div>
                    <Badge tone="blue">{pool.length} in pool</Badge>
                  </div>
                  <ul className="max-h-64 space-y-2 overflow-y-auto pr-1">
                    {pool.map((job) => (
                      <li
                        key={job.id}
                        className={classNames(
                          'flex items-center justify-between gap-3 rounded-xl border p-3 transition',
                          String(selectedJobId) === `pool-${job.id}`
                            ? 'border-brand-300 bg-brand-50'
                            : 'border-ink-100 hover:border-brand-200',
                        )}
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-ink-800">{job.title}</p>
                          <p className="truncate text-xs text-ink-500">
                            {[job.company, job.location].filter(Boolean).join(' · ') || '—'}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn btn-sm shrink-0 bg-brand-50 text-brand-700 hover:bg-brand-100"
                          disabled={analyzing || running}
                          onClick={() => checkPoolJob(job.id)}
                        >
                          {analyzing && String(selectedJobId) === `pool-${job.id}` ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Target className="h-3 w-3" />
                          )}
                          Check compatibility
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="card card-pad">
                <SectionHeading title="Your evidence" description="What the analysis will use." />
                <div className="flex items-center gap-3 rounded-xl bg-ink-50 p-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100 text-sm font-bold text-brand-700">
                    {resume.profile?.skills?.length || 0}
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-ink-800">Technical skills</p>
                    <p className="truncate text-[11px] text-ink-500">{(resume.profile?.skills || []).slice(0, 8).join(', ')}</p>
                  </div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-center">
                  <div className="rounded-xl border border-ink-100 p-3">
                    <p className="text-lg font-bold text-ink-900">{resume.profile?.projects?.length || 0}</p>
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">Projects</p>
                  </div>
                  <div className="rounded-xl border border-ink-100 p-3">
                    <p className="text-lg font-bold text-ink-900">{resume.profile?.years_experience || 0}</p>
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">Years exp.</p>
                  </div>
                </div>
                <Link to="/resume" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700">
                  Improve your resume <ArrowRight className="h-3 w-3" />
                </Link>
              </div>

              <div className="card card-pad">
                <SectionHeading title="Recent analyses" />
                {history.length ? (
                  <ul className="space-y-1">
                    {history.slice(0, 5).map((item) => (
                      <li key={item.id}>
                        <button
                          onClick={() => {
                            api
                              .getCompatibility(item.id)
                              .then((data) => {
                                setResult(data)
                                setFull(null)
                              })
                              .catch((e) => setError(apiError(e)))
                          }}
                          className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left hover:bg-ink-50"
                        >
                          <span
                            className={classNames(
                              'flex h-8 w-8 items-center justify-center rounded-lg text-[11px] font-bold',
                              item.overall_score >= 65 ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600',
                            )}
                          >
                            {Math.round(item.overall_score)}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-semibold text-ink-800">{item.job_title || 'Role'}</span>
                            <span className="text-[10px] text-ink-400">{fmtDate(item.created_at)}</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-ink-400">Your analyses will appear here.</p>
                )}
              </div>
            </div>
          </div>

          {(analyzing || running) && !result && (
            <div className="card card-pad">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                  <Loader2 className="h-5 w-5 animate-spin" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-ink-800">
                    {running ? 'The supervisor is coordinating five agents…' : 'Scoring your evidence…'}
                  </p>
                  <p className="text-xs text-ink-500">
                    {running ? 'Resume → job → compatibility → gaps → interview questions.' : 'Embeddings and weighted scoring, no invented percentages.'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {full?.activity && (
                <AgentActivity
                  activity={full.activity}
                  providers={full.providers}
                  engine={full.engine}
                  errors={full.errors}
                />
              )}
              <div className="grid gap-6 xl:grid-cols-5" ref={reportRef}>
                <div className="xl:col-span-2">
                  <ScoreCard report={report} score={result.overall_score} verdict={report?.verdict} />
                  <div className="mt-4 flex flex-wrap gap-2">
                    {result.gap_id && (
                      <Link to={`/skill-gap?gap=${result.gap_id}`} className="btn-secondary btn-sm">
                        <ListChecks className="h-3.5 w-3.5" /> View roadmap
                      </Link>
                    )}
                    <Link to="/interview-prep" className="btn-secondary btn-sm">
                      <FileSearch className="h-3.5 w-3.5" /> Interview questions
                    </Link>
                    <button
                      className="btn-primary btn-sm"
                      onClick={() => navigate('/mock-interview', { state: { compatibilityId: result.id } })}
                    >
                      <PlayCircle className="h-3.5 w-3.5" /> Practise
                    </button>
                  </div>
                </div>
                <div className="card card-pad xl:col-span-3">
                  <SectionHeading
                    title="Category breakdown"
                    description="Weights: skills 40% · experience 25% · projects 20% · education 10% · certifications 5%."
                  />
                  <CategoryBars categories={report?.category_scores || []} />
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {(report?.category_scores || []).map((category) => (
                      <p key={category.name} className="rounded-lg bg-ink-50 px-2.5 py-2 text-[11px] leading-relaxed text-ink-500">
                        <span className="font-semibold text-ink-600">{category.name}:</span> {category.explanation}
                      </p>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <SkillGroup
                  title="Matched"
                  tone={{ icon: 'text-emerald-500', badge: 'green', chip: 'border-emerald-200 bg-emerald-50 text-emerald-700' }}
                  items={report?.matched_skills || []}
                  icon={CheckCircle2}
                  emptyText="No direct matches yet."
                />
                <SkillGroup
                  title="Partial"
                  tone={{ icon: 'text-amber-500', badge: 'amber', chip: 'border-amber-200 bg-amber-50 text-amber-700' }}
                  items={report?.partially_matched_skills || []}
                  icon={CircleDot}
                  emptyText="No near-matches."
                />
                <SkillGroup
                  title="Missing"
                  tone={{ icon: 'text-red-500', badge: 'red', chip: 'border-red-200 bg-red-50 text-red-700' }}
                  items={report?.missing_skills || []}
                  icon={XCircle}
                  emptyText="No missing required skills."
                />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <div className="card card-pad">
                  <SectionHeading title="Evidence used" description="Sentences from your resume that support the score." />
                  <ul className="space-y-2.5">
                    {(report?.evidence || []).map((item, i) => (
                      <li key={i} className="flex gap-2 rounded-lg bg-ink-50 px-3 py-2 text-xs leading-relaxed text-ink-600">
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-400" /> {item}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="grid gap-4">
                  <div className="card card-pad">
                    <SectionHeading title="Strengths" />
                    <ul className="space-y-2">
                      {(report?.strengths || []).map((item, i) => (
                        <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="card card-pad">
                    <SectionHeading title="Concerns to address" />
                    <ul className="space-y-2">
                      {(report?.concerns || []).map((item, i) => (
                        <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {selectedJob && !result && (
            <p className="text-center text-xs text-ink-400">
              Selected: {selectedJob.title} {selectedJob.company ? `at ${selectedJob.company}` : ''}
            </p>
          )}
        </>
      )}
    </div>
  )
}
