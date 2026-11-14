import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Award,
  BriefcaseBusiness,
  CheckCircle2,
  FileText,
  FolderOpen,
  GraduationCap,
  Mail,
  MapPin,
  Phone,
  Sparkles,
  Target,
  Upload,
  UserRound,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { classNames, fmtDate, initials } from '../services/utils'
import { EmptyState, ErrorBanner, LoadingBlock, SectionHeading } from '../components/ui'

const MAX_MB = 10

function scoreTone(score) {
  if (score >= 75) return 'text-emerald-600'
  if (score >= 50) return 'text-amber-600'
  return 'text-rose-600'
}

export default function Profile() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [resume, setResume] = useState(null)
  const [resumes, setResumes] = useState([])
  const [analyses, setAnalyses] = useState([])
  const [pool, setPool] = useState([])
  const [pipeline, setPipeline] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')

  useEffect(() => {
    Promise.allSettled([
      api.getResume(),
      api.listResumes(),
      api.listCompatibility(),
      api.listPool(),
      api.listPipeline(),
    ]).then(([res, resList, comp, poolRes, pipe]) => {
      if (res.status === 'fulfilled') setResume(res.value)
      if (resList.status === 'fulfilled') setResumes(resList.value || [])
      if (comp.status === 'fulfilled') setAnalyses(comp.value || [])
      if (poolRes.status === 'fulfilled') setPool(poolRes.value?.jobs || [])
      if (pipe.status === 'fulfilled') setPipeline(pipe.value?.entries || [])
      setLoading(false)
    })
  }, [])

  async function upload(file) {
    if (!file) return
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'docx', 'txt', 'md'].includes(ext)) {
      setError('Upload a PDF, DOCX, TXT or MD file.')
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File is larger than ${MAX_MB} MB.`)
      return
    }
    setBusy(true)
    setError('')
    setNote('')
    setProgress(0)
    try {
      const data = await api.uploadResume(file, setProgress)
      setResume(data)
      setResumes(await api.listResumes())
      setNote(
        `Uploaded ${data.filename}. It is stored as a PDF and is now your active resume — older versions stay in your library.`
      )
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusy(false)
    }
  }

  async function openResume() {
    if (!resume?.id) return
    try {
      const blob = await api.downloadResume(resume.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${resume.filename?.replace(/\.[^.]+$/, '') || 'resume'}.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (e) {
      setError(apiError(e))
    }
  }

  if (loading) return <LoadingBlock label="Loading your profile…" />

  const profile = resume?.profile || {}
  const skills = profile.skills || []
  const experience = profile.experience || []
  const projects = profile.projects || []
  const education = profile.education || []
  const certifications = profile.certifications || []
  const completeFields = [
    profile.name,
    profile.email,
    profile.summary,
    skills.length,
    education.length,
    experience.length,
    projects.length,
  ].filter((v) => (Array.isArray(v) ? v.length : Boolean(v))).length

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      {/* Identity header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] p-6 text-white shadow-lift sm:p-8">
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="flex items-start gap-4">
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/10 text-xl font-bold">
              {initials(profile?.name)}
            </span>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/80">
                My profile
              </p>
              <h2 className="mt-1 text-2xl font-bold tracking-tight">{profile?.name || 'Candidate'}</h2>
              {profile?.headline && (
                <p className="mt-0.5 text-sm text-brand-100/80">{profile.headline}</p>
              )}
              <div className="mt-3 flex flex-wrap gap-3 text-xs text-brand-100/70">
                {profile?.email && (
                  <span className="flex items-center gap-1">
                    <Mail className="h-3 w-3" /> {profile.email}
                  </span>
                )}
                {profile?.phone && (
                  <span className="flex items-center gap-1">
                    <Phone className="h-3 w-3" /> {profile.phone}
                  </span>
                )}
                {profile?.location && (
                  <span className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" /> {profile.location}
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={busy}
              className="btn bg-white text-brand-900 hover:bg-brand-50 btn-sm"
            >
              <Upload className="h-3 w-3" />
              {busy ? 'Parsing…' : 'Upload new résumé'}
            </button>
            <button
              type="button"
              onClick={openResume}
              disabled={!resume?.id}
              className="btn border-white/20 bg-white/10 text-white hover:bg-white/20 btn-sm"
            >
              <FileText className="h-3 w-3" /> Open my résumé (PDF)
            </button>
          </div>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={(e) => upload(e.target.files?.[0])}
        />

        {busy && (
          <p className="relative mt-4 text-xs text-brand-100/70">
            Uploading {progress}% · extracting profile…
          </p>
        )}
        {note && (
          <p className="relative mt-4 rounded-xl bg-emerald-400/15 px-3 py-2 text-xs text-emerald-100">
            {note}
          </p>
        )}

        <div className="relative mt-6 grid gap-3 sm:grid-cols-4">
          {[
            ['Profile completeness', `${Math.round((completeFields / 7) * 100)}%`],
            ['Technical skills', skills.length],
            ['Pool jobs', pool.length],
            ['Analyses run', analyses.length],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl bg-white/10 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-brand-200/70">
                {label}
              </p>
              <p className="mt-0.5 text-lg font-bold">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Skills */}
          <section className="card card-pad">
            <SectionHeading title="My skills" />
            {skills.length ? (
              <div className="flex flex-wrap gap-1.5">
                {skills.map((s) => (
                  <span key={s} className="chip chip-blue">
                    {s}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink-400">
                No skills detected yet — upload a résumé to populate this.
              </p>
            )}
            {profile?.soft_skills?.length ? (
              <>
                <p className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                  Soft skills
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {profile.soft_skills.map((s) => (
                    <span key={s} className="chip">
                      {s}
                    </span>
                  ))}
                </div>
              </>
            ) : null}
          </section>

          {/* Experience / projects / education */}
          <section className="card card-pad space-y-6">
            <SectionHeading title="My experience" />
            {experience.length ? (
              <div className="space-y-3">
                {experience.map((item, i) => (
                  <div key={i} className="rounded-2xl border border-ink-100 p-4">
                    <p className="text-sm font-semibold text-ink-800">{item.title}</p>
                    <p className="text-xs text-ink-500">
                      {[item.company, item.duration].filter(Boolean).join(' · ')}
                    </p>
                    {item.highlights?.length ? (
                      <ul className="mt-2 space-y-1">
                        {item.highlights.map((h, j) => (
                          <li key={j} className="flex gap-2 text-xs text-ink-600">
                            <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500" />
                            {h}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink-400">No experience entries detected.</p>
            )}

            {projects.length > 0 && (
              <div>
                <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-800">
                  <FolderOpen className="h-4 w-4 text-brand-600" /> Projects
                </h4>
                <div className="space-y-2">
                  {projects.map((p, i) => (
                    <div key={i} className="rounded-xl bg-ink-50 p-3">
                      <p className="text-sm font-semibold text-ink-800">{p.name}</p>
                      {p.description && (
                        <p className="mt-0.5 text-xs leading-relaxed text-ink-600">{p.description}</p>
                      )}
                      {p.tech?.length ? (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {p.tech.map((t) => (
                            <span key={t} className="chip text-[10px]">
                              {t}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {education.length > 0 && (
              <div>
                <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-800">
                  <GraduationCap className="h-4 w-4 text-brand-600" /> Education
                </h4>
                <div className="space-y-2">
                  {education.map((e, i) => (
                    <div key={i} className="rounded-xl bg-ink-50 p-3">
                      <p className="text-sm font-semibold text-ink-800">{e.degree}</p>
                      <p className="text-xs text-ink-500">
                        {[e.institution, e.year].filter(Boolean).join(' · ')}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {certifications.length > 0 && (
              <div>
                <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-800">
                  <Award className="h-4 w-4 text-brand-600" /> Certifications
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {certifications.map((c, i) => (
                    <span key={i} className="chip chip-green">
                      {c.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Resume library */}
          <section className="card card-pad">
            <SectionHeading title="My résumé versions" />
            {resumes.length ? (
              <ul className="divide-y divide-ink-100">
                {resumes.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-800">
                        {r.filename || 'Untitled résumé'}
                      </p>
                      <p className="text-xs text-ink-400">
                        {fmtDate(r.created_at)} · {r.provider}
                        {r.id === resume?.id ? ' · active' : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => navigate('/resume')}
                      >
                        View
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-400">No résumé uploaded yet.</p>
            )}
          </section>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <section className="card card-pad">
            <SectionHeading title="My job pool" />
            {pool.length ? (
              <ul className="space-y-2">
                {pool.slice(0, 6).map((job) => (
                  <li key={job.id} className="rounded-xl border border-ink-100 p-3">
                    <p className="truncate text-sm font-semibold text-ink-800">{job.title}</p>
                    <p className="text-xs text-ink-500">
                      {[job.company, job.location].filter(Boolean).join(' · ')}
                    </p>
                    {job.fit_score ? (
                      <p className={classNames('mt-1 text-xs font-semibold', scoreTone(job.fit_score))}>
                        {Math.round(job.fit_score)}% fit
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-400">Your pool is empty.</p>
            )}
            <Link to="/jobs" className="btn btn-sm mt-3 w-full justify-center">
              Browse more jobs
            </Link>
          </section>

          <section className="card card-pad">
            <SectionHeading title="My recent analyses" />
            {analyses.length ? (
              <ul className="space-y-2">
                {analyses.slice(0, 6).map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-800">
                        {a.job_title || 'Job analysis'}
                      </p>
                      <p className="text-xs text-ink-400">{fmtDate(a.created_at)}</p>
                    </div>
                    <span className={classNames('text-sm font-bold', scoreTone(a.overall_score))}>
                      {Math.round(a.overall_score)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-400">No analyses yet.</p>
            )}
            <Link to="/compatibility" className="btn btn-sm mt-3 w-full justify-center">
              <Target className="h-3 w-3" /> Check compatibility
            </Link>
          </section>

          {pipeline.length > 0 && (
            <section className="card card-pad">
              <SectionHeading title="Applications I'm tracking" />
              <ul className="space-y-2">
                {pipeline.slice(0, 6).map((entry) => (
                  <li key={entry.id} className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-800">{entry.title}</p>
                      <p className="text-xs text-ink-400">{entry.company || '—'}</p>
                    </div>
                    <span className="chip text-[10px]">{entry.status}</span>
                  </li>
                ))}
              </ul>
              <Link to="/pipeline" className="btn btn-sm mt-3 w-full justify-center">
                <BriefcaseBusiness className="h-3 w-3" /> Open pipeline
              </Link>
            </section>
          )}

          {!resume && (
            <EmptyState
              icon={UserRound}
              title="No résumé yet"
              text="Upload a résumé to unlock skills, compatibility and interviews."
            />
          )}
        </div>
      </div>

      {profile?.summary && (
        <section className="card card-pad">
          <SectionHeading title="My summary" />
          <p className="text-sm leading-relaxed text-ink-600">{profile.summary}</p>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-ink-400">
            <Sparkles className="h-3 w-3" /> Extracted from your uploaded résumé — edit by uploading a new version.
          </p>
        </section>
      )}
    </div>
  )
}
