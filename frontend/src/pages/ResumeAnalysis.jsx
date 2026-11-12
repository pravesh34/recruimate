import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronDown,
  GraduationCap,
  Lightbulb,
  Mail,
  MapPin,
  Phone,
  Sparkles,
  Upload,
  UserRound,
  XCircle,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { classNames, fmtDate, initials } from '../services/utils'
import { EmptyState, ErrorBanner, LoadingBlock, ProgressBar, SectionHeading } from '../components/ui'

const MAX_MB = 10

function UploadZone({ onUploaded, onError }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [busy, setBusy] = useState(false)

  async function handleFile(file) {
    if (!file) return
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'docx', 'txt', 'md'].includes(ext)) {
      onError('Upload a PDF, DOCX, TXT or MD file.')
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      onError(`File is larger than ${MAX_MB} MB.`)
      return
    }
    setBusy(true)
    setProgress(0)
    onError('')
    try {
      const data = await api.uploadResume(file, setProgress)
      onUploaded(data)
    } catch (error) {
      onError(apiError(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        handleFile(e.dataTransfer.files?.[0])
      }}
      className={classNames(
        'relative overflow-hidden rounded-2xl border-2 border-dashed px-6 py-10 text-center transition',
        dragging ? 'border-brand-400 bg-brand-50/70' : 'border-ink-200 bg-white hover:border-brand-300 hover:bg-brand-50/30',
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-100 to-violet-100 text-brand-600">
        <Upload className="h-6 w-6" />
      </div>
      <h3 className="text-base font-semibold text-ink-900">Upload your resume</h3>
      <p className="mx-auto mt-1 max-w-md text-sm leading-relaxed text-ink-500">
        Drag and drop a PDF, DOCX, TXT or MD file (max {MAX_MB} MB). Text-based PDFs work best; scanned
        images cannot be read.
      </p>
      <div className="mt-5">
        <button className="btn-primary" onClick={() => inputRef.current?.click()} disabled={busy}>
          {busy ? 'Parsing…' : 'Choose a file'}
        </button>
      </div>
      {busy && (
        <div className="mx-auto mt-4 max-w-xs">
          <ProgressBar value={progress} />
          <p className="mt-1 text-[11px] text-ink-400">{progress < 100 ? `Uploading ${progress}%` : 'Extracting profile…'}</p>
        </div>
      )}
      <p className="mt-4 text-[11px] text-ink-400">
        Your file is stored locally. It is only sent to an LLM provider if you explicitly configure one.
      </p>
    </div>
  )
}

function Section({ title, icon: Icon, children, action }) {
  return (
    <div className="card card-pad">
      <SectionHeading
        title={title}
        action={action}
        description={null}
      />
      {Icon && <div className="hidden" />}
      {children}
    </div>
  )
}

export default function ResumeAnalysis() {
  const [resume, setResume] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [openExperience, setOpenExperience] = useState(0)

  useEffect(() => {
    api
      .getResume()
      .then(setResume)
      .catch((e) => {
        const status = e?.response?.status
        if (status !== 404) setError(apiError(e))
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingBlock label="Loading your resume profile…" />

  const profile = resume?.profile
  const completeFields = profile
    ? [
        profile.name,
        profile.email,
        profile.summary,
        profile.skills?.length,
        profile.education?.length,
        profile.experience?.length,
        profile.projects?.length,
      ].filter(Boolean).length
    : 0

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError('')} />

      {!resume ? (
        <div className="mx-auto max-w-2xl">
          <UploadZone onUploaded={(data) => setResume(data)} onError={setError} />
        </div>
      ) : (
        <>
          <section className="card overflow-hidden">
            <div className="relative bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] px-6 py-6 text-white">
              <div className="absolute inset-0 bg-grid opacity-30" />
              <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/10 text-xl font-bold ring-1 ring-white/20">
                    {initials(profile?.name)}
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/70">
                      Resume profile
                    </p>
                    <h2 className="text-xl font-bold tracking-tight">{profile?.name || 'Candidate'}</h2>
                    <p className="mt-0.5 text-sm text-brand-100/70">
                      {profile?.headline || 'Add a target role to sharpen your analysis'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-brand-100/70">
                      {profile?.email && <span className="flex items-center gap-1"><Mail className="h-3 w-3" /> {profile.email}</span>}
                      {profile?.phone && <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {profile.phone}</span>}
                      {profile?.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {profile.location}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-start gap-2 sm:items-end">
                  <span className="chip border-white/20 bg-white/10 text-white">
                    <Sparkles className="h-3 w-3" /> {resume.provider === 'heuristic' ? 'Local heuristics' : resume.provider}
                  </span>
                  <span className="text-[11px] text-brand-200/60">
                    {resume.filename} · {fmtDate(resume.created_at)}
                  </span>
                  <Link to="/compatibility" className="btn bg-white text-brand-900 hover:bg-brand-50 btn-sm">
                    Match to a job <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            </div>
            <div className="grid gap-4 px-6 py-4 sm:grid-cols-4">
              {[
                ['Profile completeness', `${Math.round((completeFields / 7) * 100)}%`],
                ['Technical skills', profile?.skills?.length || 0],
                ['Experience', profile?.years_experience ? `${profile.years_experience} yrs` : '—'],
                ['Projects', profile?.projects?.length || 0],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">{label}</p>
                  <p className="mt-1 text-lg font-bold text-ink-900">{value}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="grid gap-6 xl:grid-cols-3">
            <div className="space-y-6 xl:col-span-2">
              {profile?.summary && (
                <div className="card card-pad">
                  <SectionHeading title="Professional summary" />
                  <p className="text-sm leading-relaxed text-ink-600">{profile.summary}</p>
                </div>
              )}

              <Section title="Skills">
                <div className="flex flex-wrap gap-1.5">
                  {(profile?.skills || []).map((skill) => (
                    <span key={skill} className="chip-blue">{skill}</span>
                  ))}
                  {(profile?.soft_skills || []).map((skill) => (
                    <span key={skill} className="chip-violet">{skill}</span>
                  ))}
                  {!profile?.skills?.length && <p className="text-sm text-ink-500">No technical skills detected.</p>}
                </div>
              </Section>

              <Section title="Experience">
                {profile?.experience?.length ? (
                  <div className="space-y-3">
                    {profile.experience.map((item, index) => (
                      <div key={index} className="rounded-xl border border-ink-100 bg-ink-50/40">
                        <button
                          className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
                          onClick={() => setOpenExperience(openExperience === index ? -1 : index)}
                        >
                          <div className="flex gap-3">
                            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-100 text-brand-600">
                              <BriefcaseBusiness className="h-4 w-4" />
                            </span>
                            <div>
                              <p className="text-sm font-semibold text-ink-800">{item.title || 'Role'}</p>
                              <p className="text-xs text-ink-500">
                                {[item.company, item.start].filter(Boolean).join(' · ')}
                              </p>
                            </div>
                          </div>
                          <ChevronDown
                            className={classNames('mt-1 h-4 w-4 text-ink-400 transition', openExperience === index && 'rotate-180')}
                          />
                        </button>
                        {openExperience === index && (
                          <div className="border-t border-ink-100 px-4 py-3">
                            {item.highlights?.length ? (
                              <ul className="space-y-1.5">
                                {item.highlights.map((highlight, i) => (
                                  <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-400" />
                                    {highlight}
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-xs text-ink-500">{item.description || 'No details extracted.'}</p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-ink-500">No experience entries detected. Add internships, freelance or open-source work.</p>
                )}
              </Section>

              <Section title="Projects">
                {profile?.projects?.length ? (
                  <div className="space-y-3">
                    {profile.projects.map((project, index) => (
                      <div key={index} className="rounded-xl border border-ink-100 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h4 className="text-sm font-semibold text-ink-800">{project.name}</h4>
                          <div className="flex flex-wrap gap-1">
                            {(project.technologies || []).slice(0, 5).map((tech) => (
                              <span key={tech} className="chip">{tech}</span>
                            ))}
                          </div>
                        </div>
                        <p className="mt-1.5 text-xs leading-relaxed text-ink-500">{project.description}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-ink-500">No projects detected. Projects are the strongest evidence for early-career roles.</p>
                )}
              </Section>

              <div className="grid gap-6 md:grid-cols-2">
                <Section title="Education">
                  {profile?.education?.length ? (
                    <div className="space-y-3">
                      {profile.education.map((item, index) => (
                        <div key={index} className="flex gap-3">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-50 text-violet-600">
                            <GraduationCap className="h-4 w-4" />
                          </span>
                          <div>
                            <p className="text-sm font-semibold text-ink-800">{item.degree}</p>
                            <p className="text-xs text-ink-500">{item.institution}</p>
                            <p className="text-[11px] text-ink-400">
                              {[item.start_year, item.end_year].filter(Boolean).join(' – ')}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-ink-500">No education detected.</p>
                  )}
                </Section>
                <Section title="Certifications & achievements">
                  {profile?.certifications?.length || profile?.achievements?.length ? (
                    <ul className="space-y-2">
                      {(profile.certifications || []).map((item, i) => (
                        <li key={`cert-${i}`} className="flex gap-2 text-xs text-ink-600">
                          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> {item}
                        </li>
                      ))}
                      {(profile.achievements || []).map((item, i) => (
                        <li key={`ach-${i}`} className="flex gap-2 text-xs text-ink-600">
                          <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> {item}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-ink-500">No certifications or awards detected.</p>
                  )}
                </Section>
              </div>
            </div>

            <div className="space-y-6">
              <div className="card card-pad">
                <SectionHeading title="Strengths" />
                <ul className="space-y-2.5">
                  {(profile?.resume_strengths || []).map((item, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" /> {item}
                    </li>
                  ))}
                  {!profile?.resume_strengths?.length && (
                    <li className="text-xs text-ink-500">Upload a richer resume to surface strengths.</li>
                  )}
                </ul>
              </div>

              <div className="card card-pad">
                <SectionHeading title="Weaknesses to fix" />
                <ul className="space-y-2.5">
                  {(profile?.resume_weaknesses || []).map((item, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-600">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" /> {item}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="card card-pad bg-gradient-to-br from-brand-50 to-violet-50/60">
                <SectionHeading title="Improvement suggestions" />
                <ul className="space-y-2.5">
                  {(profile?.improvement_suggestions || []).map((item, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-ink-700">
                      <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500" /> {item}
                    </li>
                  ))}
                </ul>
                <p className="mt-4 rounded-xl bg-white/70 px-3 py-2 text-[11px] leading-relaxed text-ink-500">
                  Suggestions never invent experience. Rewrite with what you actually did, using action → tool → result.
                </p>
              </div>

              {profile?.unknown_fields?.length > 0 && (
                <div className="card card-pad">
                  <SectionHeading title="Not detected" />
                  <div className="flex flex-wrap gap-1.5">
                    {profile.unknown_fields.map((field) => (
                      <span key={field} className="chip-red">
                        <XCircle className="h-3 w-3" /> {field}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <button
                className="btn-secondary w-full"
                onClick={() => setResume(null)}
              >
                <Upload className="h-4 w-4" /> Upload a newer version
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
